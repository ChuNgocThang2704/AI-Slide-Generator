# Build stage
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# Run stage
FROM nginx:stable-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80

# Tìm chuỗi mật mã __API_URL_PLACEHOLDER__ và thay bằng biến VITE_API_BASE_URL từ Render
CMD ["/bin/sh", "-c", "sed -i 's|__API_URL_PLACEHOLDER__|'\"${VITE_API_BASE_URL}\"'|g' /usr/share/nginx/html/assets/*.js && nginx -g 'daemon off;'"]
