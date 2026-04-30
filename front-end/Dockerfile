# Build stage
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
# Ở đây KHÔNG khai báo ARG hay ENV gì cả. 
# Vite sẽ buộc phải dùng giá trị mặc định trong axios.ts là '__API_URL_PLACEHOLDER__'
RUN npm run build

# Run stage
FROM nginx:stable-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80

# Chỉ thay thế mật mã bằng URL THẬT lúc container bắt đầu chạy trên Render
CMD ["/bin/sh", "-c", "sed -i 's|__API_URL_PLACEHOLDER__|'\"${VITE_API_BASE_URL}\"'|g' /usr/share/nginx/html/assets/*.js && nginx -g 'daemon off;'"]
