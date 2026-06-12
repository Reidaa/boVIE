export type JobPayload = {
  id: number;
  missionTitle?: string;
  countryName?: string;
  organizationName?: string;
};

export type JobDiscoveredEvent = {
  schemaVersion: number;
  source: string;
  discoveredAt: string;
  offerId: number;
  job: JobPayload;
};
