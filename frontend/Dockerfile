FROM node:20-alpine

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

EXPOSE 5173
# Для MVP запускаем dev-сервер Vite. Для прода: npm run build + статика через nginx.
CMD ["npm", "run", "dev"]
