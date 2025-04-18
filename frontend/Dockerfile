# ---- Stage 1: Build the React App ----
FROM node:18 as builder

WORKDIR /app

# Copy package files and install dependencies (including devDependencies)
COPY package*.json ./
RUN npm install

# Copy the rest of the source code
COPY . .

# Build the optimized static files (output usually goes to 'dist' directory)
RUN npm run build

# ---- Stage 2: Serve static files with Nginx ----
FROM nginx:1.25-alpine

# Copy the custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy the static build artifacts from the 'builder' stage
# The source path '/app/dist' depends on Vite's build output directory (check vite.config.js if needed)
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose port 80 (Nginx default)
EXPOSE 80

# Nginx image's default command starts the server
# No explicit CMD needed unless overriding Nginx defaults
