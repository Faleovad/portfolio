FROM node:24-alpine AS build
WORKDIR /console
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /console/dist /usr/share/nginx/html
