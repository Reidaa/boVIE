import { type DisplayField, DisplayFieldSchema } from "@bovie/offer-events";
import { externalApplicationUrl, type Job } from "./job.js";

function formatDateDmy(iso: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso.trim());
  if (match) {
    return `${match[3]}/${match[2]}/${match[1]}`;
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    throw new Error(`Invalid ISO date: ${iso}`);
  }
  const dd = String(date.getUTCDate()).padStart(2, "0");
  const mm = String(date.getUTCMonth() + 1).padStart(2, "0");
  return `${dd}/${mm}/${date.getUTCFullYear()}`;
}

export function displayFields(job: Job): DisplayField[] {
  const start = formatDateDmy(job.missionStartDate);
  const end = formatDateDmy(job.missionEndDate);
  const specializations =
    job.specializations && job.specializations.length > 0
      ? job.specializations.map((s) => s.specializationLabel).join(", ")
      : "N/A";
  const posted = job.creationDate ? formatDateDmy(job.creationDate) : "N/A";
  const externalUrl = externalApplicationUrl(job);
  const applicationValue = externalUrl ? `[Site externe](${externalUrl})` : "Business France";

  const fields = [
    { name: ":hot_springs: Entreprise", value: job.organizationName },
    { name: ":satellite_orbital: Posté le", value: posted },
    { name: ":calendar: Durée", value: `${job.missionDuration} mois` },
    { name: ":gear: Secteur", value: job.activitySectorN1 || "N/A" },
    { name: ":world_map: Pays", value: job.countryName },
    { name: ":cityscape: Ville", value: job.cityName || "N/A" },
    { name: ":money_with_wings: Salaire", value: `${job.indemnite}e` },
    { name: ":person_running: Début", value: start },
    { name: ":checkered_flag: Fin", value: end },
    { name: ":e_mail: Email", value: job.contactEmail || "N/A" },
    { name: ":person_bald: Contact", value: job.contactName || "N/A" },
    {
      name: ":globe_with_meridians: Business France",
      value: `[Voir offre](https://mon-vie-via.businessfrance.fr/offres/${job.id})`,
    },
    { name: ":outbox_tray: Application", value: applicationValue },
    { name: ":label: Specialization(s)", value: specializations },
  ];

  // The event contract caps values at 1024 characters, like Discord's embed fields.
  return fields
    .filter((field) => field.value.length > 0)
    .map((field) =>
      DisplayFieldSchema.parse({
        name: field.name,
        value: field.value.slice(0, 1024),
      }),
    );
}
