// Package mysqlcommon provides MySQL connections, UTC timestamps, queue leases, and migration execution.
package mysqlcommon

import (
	"database/sql"
	"errors"
	"fmt"
	"net"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/Reidaa/boVIE/packages/clicommon"
	"github.com/go-sql-driver/mysql"
)

// Config holds parsed MySQL connection details. String and GoString redact credentials.
type Config struct {
	user     string
	password string
	host     string
	port     string
	database string
}

// ParseDatabaseURL parses a mysql:// or mysql+pymysql:// URL into a Config.
// Errors never echo the raw URL or password.
func ParseDatabaseURL(raw string) (*Config, error) {
	if strings.TrimSpace(raw) == "" {
		return nil, errors.New("DATABASE_URL must be a MySQL URL")
	}
	parsed, err := url.Parse(raw)
	if err != nil {
		return nil, errors.New("DATABASE_URL must be a MySQL URL")
	}
	if parsed.Scheme != "mysql" && parsed.Scheme != "mysql+pymysql" {
		return nil, errors.New("use mysql://user:password@host/database")
	}
	if parsed.User == nil || parsed.User.Username() == "" {
		return nil, errors.New("use mysql://user:password@host/database")
	}
	host := parsed.Hostname()
	if host == "" {
		return nil, errors.New("use mysql://user:password@host/database")
	}
	port := parsed.Port()
	if port == "" {
		port = "3306"
	} else if _, err := strconv.Atoi(port); err != nil {
		return nil, errors.New("DATABASE_URL must be a MySQL URL")
	}
	database := strings.TrimPrefix(parsed.Path, "/")
	if database == "" || strings.Contains(database, "/") {
		return nil, errors.New("use mysql://user:password@host/database")
	}
	password, _ := parsed.User.Password()
	return &Config{
		user:     parsed.User.Username(),
		password: password,
		host:     host,
		port:     port,
		database: database,
	}, nil
}

// LoadEnv loads .env (without overriding process env) and parses DATABASE_URL.
func LoadEnv() (*Config, error) {
	clicommon.LoadDotEnv()
	return ParseDatabaseURL(os.Getenv("DATABASE_URL"))
}

// Database returns the target database name.
func (c *Config) Database() string {
	return c.database
}

// User returns the MySQL username.
func (c *Config) User() string {
	return c.user
}

// Password returns the decoded MySQL password.
func (c *Config) Password() string {
	return c.password
}

// Host returns the MySQL hostname.
func (c *Config) Host() string {
	return c.host
}

// Port returns the MySQL port.
func (c *Config) Port() string {
	return c.port
}

// WithoutDatabase returns a copy targeting the MySQL server without selecting a database.
func (c *Config) WithoutDatabase() *Config {
	cp := *c
	cp.database = ""
	return &cp
}

// WithDatabase returns a copy targeting the given database name.
func (c *Config) WithDatabase(name string) *Config {
	cp := *c
	cp.database = name
	return &cp
}

// WithCredentials returns a copy with the given username and password.
func (c *Config) WithCredentials(user, password string) *Config {
	cp := *c
	cp.user = user
	cp.password = password
	return &cp
}

// String redacts credentials so secrets are never printed in logs or debug output.
func (c *Config) String() string {
	return fmt.Sprintf("mysql://%s:***@%s/%s", c.user, net.JoinHostPort(c.host, c.port), c.database)
}

// GoString redacts credentials for %#v formatting.
func (c *Config) GoString() string {
	return c.String()
}

// FormatDSN produces the go-sql-driver/mysql DSN with UTC time parsing and timeouts.
func (c *Config) FormatDSN() string {
	mc := mysql.NewConfig()
	mc.User = c.user
	mc.Passwd = c.password
	mc.Net = "tcp"
	mc.Addr = net.JoinHostPort(c.host, c.port)
	mc.DBName = c.database
	mc.ParseTime = true
	mc.Loc = time.UTC
	mc.Timeout = 10 * time.Second
	mc.ReadTimeout = 30 * time.Second
	mc.WriteTimeout = 30 * time.Second
	mc.AllowNativePasswords = true
	mc.Params = map[string]string{
		"charset": "utf8mb4",
	}
	return mc.FormatDSN()
}

// OpenDB returns a configured *sql.DB pool without opening a network connection yet.
func OpenDB(cfg *Config) (*sql.DB, error) {
	db, err := sql.Open("mysql", cfg.FormatDSN())
	if err != nil {
		return nil, err
	}
	db.SetConnMaxLifetime(30 * time.Minute)
	db.SetMaxOpenConns(10)
	db.SetMaxIdleConns(5)
	return db, nil
}
