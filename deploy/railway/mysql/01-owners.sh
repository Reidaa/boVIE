# Sourced by the official MySQL entrypoint on a fresh data volume.
# Railway generates alphanumeric passwords. Reject SQL metacharacters here.
for variable in BF_DATABASE_PASSWORD WTTJ_DATABASE_PASSWORD NOTIFICATION_DATABASE_PASSWORD; do
    if [[ ! ${!variable:-} =~ ^[a-zA-Z0-9_-]{32,128}$ ]]; then
        echo "Set $variable to a generated 32-128 character alphanumeric password." >&2
        exit 1
    fi
done

docker_process_sql <<EOSQL
CREATE DATABASE business_france CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;
CREATE DATABASE wttj CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;
CREATE DATABASE notifications CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;
CREATE USER 'business_france'@'%' IDENTIFIED BY '${BF_DATABASE_PASSWORD}';
CREATE USER 'wttj'@'%' IDENTIFIED BY '${WTTJ_DATABASE_PASSWORD}';
CREATE USER 'notifications'@'%' IDENTIFIED BY '${NOTIFICATION_DATABASE_PASSWORD}';
GRANT ALL PRIVILEGES ON business_france.* TO 'business_france'@'%';
GRANT ALL PRIVILEGES ON wttj.* TO 'wttj'@'%';
GRANT ALL PRIVILEGES ON notifications.* TO 'notifications'@'%';
EOSQL
