module.exports = {
  apps: [
    {
      name: "homie-backend",
      cwd: "./backend",
      interpreter: "none",
      script: ".venv/bin/uvicorn",
      args: "main:app --host 0.0.0.0 --port 8000",
      watch: false,
      autorestart: true,
      env: {
        PYTHONPATH: ".",
      },
    },
    {
      name: "homie-frontend",
      cwd: "./frontend",
      script: "node_modules/.bin/next",
      args: "start --port 3000",
      watch: false,
      autorestart: true,
    },
  ],
};
