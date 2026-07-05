FROM node:20-slim

WORKDIR /app

# Install deps first (cached until package manifests change).
COPY package.json package-lock.json ./
RUN npm install

# Source is bind-mounted in dev (see docker-compose.yml); COPY makes the image
# self-contained if run without the mount.
COPY . .

EXPOSE 5173

# --host 0.0.0.0 is required so Vite (and its HMR socket) is reachable from the host.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
