module.exports = {
  apps: [{
    name: 'hls-webhook',
    script: 'webhook',
    args: '-hooks hooks.json -port 9000 -verbose',
    cwd: '/home/clide/hls',
    autorestart: true,
    watch: false,
    max_memory_restart: '500M',
    error_file: 'logs/webhook-error.log',
    out_file: 'logs/webhook-out.log',
    log_file: 'logs/webhook-combined.log',
    time: true,
    env: {
      NODE_ENV: 'production'
    }
  }]
};