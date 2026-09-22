-- Disposable/local development accounts. Provision independent secrets in production.
CREATE DATABASE business_france CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;
CREATE DATABASE wttj CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;
CREATE DATABASE notifications CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;
CREATE USER 'business_france'@'%' IDENTIFIED BY 'local-bf-only';
CREATE USER 'wttj'@'%' IDENTIFIED BY 'local-wttj-only';
CREATE USER 'notifications'@'%' IDENTIFIED BY 'local-notifications-only';
GRANT ALL PRIVILEGES ON business_france.* TO 'business_france'@'%';
GRANT ALL PRIVILEGES ON wttj.* TO 'wttj'@'%';
GRANT ALL PRIVILEGES ON notifications.* TO 'notifications'@'%';
