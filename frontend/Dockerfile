FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --loglevel info 2>&1 && echo "npm install завершён"
COPY . .
RUN echo "Сборка frontend..." && npm run build 2>&1 && echo "Сборка завершена"

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
