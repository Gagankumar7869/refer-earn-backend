CREATE DATABASE IF NOT EXISTS refer_earn
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE DATABASE IF NOT EXISTS refer_earn_test
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'refer_user'@'localhost' IDENTIFIED BY 'refer_pass_123';
CREATE USER IF NOT EXISTS 'refer_user'@'127.0.0.1' IDENTIFIED BY 'refer_pass_123';

GRANT ALL PRIVILEGES ON refer_earn.* TO 'refer_user'@'localhost';
GRANT ALL PRIVILEGES ON refer_earn_test.* TO 'refer_user'@'localhost';
GRANT ALL PRIVILEGES ON refer_earn.* TO 'refer_user'@'127.0.0.1';
GRANT ALL PRIVILEGES ON refer_earn_test.* TO 'refer_user'@'127.0.0.1';

FLUSH PRIVILEGES;