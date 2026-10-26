-- Disposable/local development accounts. Provision independent secrets in production.
CREATE DATABASE collector_business_france CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;
CREATE DATABASE collector_wttj CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;
CREATE DATABASE discord CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;
CREATE USER 'collector_business_france'@'%' IDENTIFIED BY 'local-collector-business-france-only';
CREATE USER 'collector_wttj'@'%' IDENTIFIED BY 'local-collector-wttj-only';
CREATE USER 'discord'@'%' IDENTIFIED BY 'local-discord-only';
GRANT ALL PRIVILEGES ON collector_business_france.* TO 'collector_business_france'@'%';
GRANT ALL PRIVILEGES ON collector_wttj.* TO 'collector_wttj'@'%';
GRANT ALL PRIVILEGES ON discord.* TO 'discord'@'%';
