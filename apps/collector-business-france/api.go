package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
	"regexp"
	"strings"
	"time"

	"github.com/Reidaa/boVIE/apps/collector-business-france/models"
)

const (
	// DefaultAPIURL is the Business France offers API base URL.
	DefaultAPIURL = "https://civiweb-api-prd.azurewebsites.net/api/Offers"
	// DefaultPublicOffersURL is the public page that embeds the current X-API-KEY.
	DefaultPublicOffersURL = "https://mon-vie-via.businessfrance.fr/offres"
)

var apiKeyPattern = regexp.MustCompile(`API_KEY:"((?:[^"\\]|\\.)*)"`)

// HTTPStatusError represents a non-2xx HTTP response from Business France.
type HTTPStatusError struct {
	StatusCode int
}

func (e *HTTPStatusError) Error() string {
	return fmt.Sprintf("Business France API returned HTTP %d", e.StatusCode)
}

// APIClient calls the Business France offers API and refreshes rotated public keys on 401.
type APIClient struct {
	BaseURL         string
	PublicOffersURL string
	HTTPClient      *http.Client
	apiKey          string
}

// NewAPIClient constructs an APIClient with default URLs and a 10-second HTTP timeout.
func NewAPIClient() *APIClient {
	return &APIClient{
		BaseURL:         DefaultAPIURL,
		PublicOffersURL: DefaultPublicOffersURL,
		HTTPClient:      &http.Client{Timeout: 10 * time.Second},
	}
}

// PublicAPIKey reads the key that the public offers page sends to the API.
func (c *APIClient) PublicAPIKey(ctx context.Context) (string, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, c.PublicOffersURL, nil)
	if err != nil {
		return "", err
	}
	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return "", err
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return "", &HTTPStatusError{StatusCode: resp.StatusCode}
	}
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", err
	}
	matches := apiKeyPattern.FindSubmatch(body)
	if len(matches) < 2 {
		return "", errors.New("business france site no longer publishes an API key")
	}
	var unescaped string
	if err := json.Unmarshal([]byte(`"`+string(matches[1])+`"`), &unescaped); err != nil {
		return "", fmt.Errorf("decode Business France API key: %w", err)
	}
	return unescaped, nil
}

func (c *APIClient) request(ctx context.Context, method, path string, body []byte) (*http.Response, error) {
	if c.apiKey == "" {
		if envKey := os.Getenv("BUSINESS_FRANCE_API_KEY"); envKey != "" {
			c.apiKey = envKey
		} else {
			key, err := c.PublicAPIKey(ctx)
			if err != nil {
				return nil, err
			}
			c.apiKey = key
		}
	}

	resp, err := c.sendWithKey(ctx, method, path, body, c.apiKey)
	if err != nil {
		return nil, err
	}
	if resp.StatusCode == http.StatusUnauthorized {
		_ = resp.Body.Close()
		slog.Info("Refreshing the Business France API key")
		key, err := c.PublicAPIKey(ctx)
		if err != nil {
			return nil, err
		}
		c.apiKey = key
		return c.sendWithKey(ctx, method, path, body, c.apiKey)
	}
	return resp, nil
}

func (c *APIClient) sendWithKey(ctx context.Context, method, path string, body []byte, key string) (*http.Response, error) {
	var bodyReader io.Reader
	if body != nil {
		bodyReader = bytes.NewReader(body)
	}
	req, err := http.NewRequestWithContext(ctx, method, strings.TrimRight(c.BaseURL, "/")+path, bodyReader)
	if err != nil {
		return nil, err
	}
	req.Header.Set("X-API-KEY", key)
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	return c.HTTPClient.Do(req)
}

// GetFromID fetches a single offer detail, returning (nil, nil) if the offer was removed (404/410).
func (c *APIClient) GetFromID(ctx context.Context, offerID int) (*models.Job, error) {
	resp, err := c.request(ctx, http.MethodGet, fmt.Sprintf("/details/%d", offerID), nil)
	if err != nil {
		slog.Error("Failed to fetch Business France offer", "offer_id", offerID, "error", err)
		return nil, err
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode == http.StatusNotFound || resp.StatusCode == http.StatusGone {
		slog.Warn("Business France offer is gone; skipping it", "offer_id", offerID)
		return nil, nil
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		err := &HTTPStatusError{StatusCode: resp.StatusCode}
		slog.Error("Failed to fetch Business France offer", "offer_id", offerID, "error", err)
		return nil, err
	}

	var job models.Job
	if err := json.NewDecoder(resp.Body).Decode(&job); err != nil {
		return nil, err
	}
	return &job, nil
}

// SearchID searches for offer IDs matching params.
func (c *APIClient) SearchID(ctx context.Context, params models.SearchParameters) ([]int, error) {
	body, err := json.Marshal(params.Normalized())
	if err != nil {
		return nil, err
	}
	slog.Debug("Searching offers", "parameters", string(body))

	resp, err := c.request(ctx, http.MethodPost, "/search", body)
	if err != nil {
		slog.Error("Failed to search Business France offers", "error", err)
		return nil, err
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		err := &HTTPStatusError{StatusCode: resp.StatusCode}
		slog.Error("Failed to search Business France offers", "error", err)
		return nil, err
	}

	var payload struct {
		Result []struct {
			ID int `json:"id"`
		} `json:"result"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		return nil, err
	}
	ids := make([]int, len(payload.Result))
	for i, item := range payload.Result {
		ids[i] = item.ID
	}
	return ids, nil
}
