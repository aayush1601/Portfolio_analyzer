# Dev server only. Production frontend is a static build on S3 + CloudFront (Phase 14).
FROM node:22-slim
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
EXPOSE 5173
CMD ["npm", "run", "dev"]
