# 阶段1: 构建
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production=false

COPY . .
RUN npm run build

# 阶段2: Nginx 服务
FROM nginx:alpine

# 安全最佳实践：使用非 root 用户
RUN addgroup -S nginxgroup && adduser -S nginxuser -G nginxgroup

COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 调整文件权限
RUN chown -R nginxuser:nginxgroup /usr/share/nginx/html

EXPOSE 80

USER nginxuser

CMD ["nginx", "-g", "daemon off;"]
