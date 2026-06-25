#!/bin/bash
if [ "$EUID" -ne 0 ]; then
  echo "Vui lòng chạy script bằng lệnh: sudo bash fix_websocket_nginx.sh"
  exit
fi

CONFIG_FILE="/etc/nginx/sites-enabled/nginx.conf"

# Remove the previously added map if exists
sed -i '/map $http_upgrade $connection_upgrade {/,/}/d' $CONFIG_FILE

# Use $http_connection to safely forward whatever connection header the client sent
sed -i 's/proxy_set_header Connection $connection_upgrade;/proxy_set_header Connection $http_connection;/g' $CONFIG_FILE
sed -i 's/proxy_set_header Connection "upgrade";/proxy_set_header Connection $http_connection;/g' $CONFIG_FILE

nginx -t && systemctl reload nginx

echo "Đã sửa file cấu hình Nginx và reload dịch vụ."
