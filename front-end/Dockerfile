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

# Script để thay thế URL API lúc khởi động container
CMD ["/bin/sh", "-c", "sed -i 's|http://localhost:8080|'\"${VITE_API_BASE_URL}\"'|g' /usr/share/nginx/html/assets/*.js && nginx -g 'daemon off;'"]
