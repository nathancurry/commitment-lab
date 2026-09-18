// Fear of Commitment - Observer Core
// Main event loop and coordination mechanism

const fs = require('fs');
const path = require('path');

class ObserverCore {
  constructor() {
    this.modules = [];
    this.events = [];
    this.startTime = new Date();
    this.running = false;
  }

  // Load observation modules
  async loadModules() {
    const modulesDir = path.join(__dirname, 'modules');
    
    try {
      const moduleFiles = await fs.promises.readdir(modulesDir);
      
      for (const file of moduleFiles) {
        if (file.endsWith('.js') && file !== 'index.js') {
          const modulePath = path.join(modulesDir, file);
          const Module = require(modulePath);
          const instance = new Module(this.dispatch.bind(this));
          this.modules.push({
            name: path.basename(file, '.js'),
            instance
          });
          console.log(`Loaded module: ${instance.constructor.name}`);
        }
      }
    } catch (error) {
      console.error('Error loading modules:', error.message);
      return false;
    }
    
    return true;
  }

  // Dispatch events from modules
  dispatch(event) {
    event.timestamp = new Date();
    this.events.push(event);
    
    // Keep only recent events to prevent memory growth
    if (this.events.length > 1000) {
      this.events = this.events.slice(-1000);
    }
  }

  // Start observation
  async start() {
    if (this.running) return true;
    
    console.log('Starting Fear of Commitment Observer Core...');
    const loaded = await this.loadModules();
    
    if (!loaded) {
      console.error('Failed to load modules');
      return false;
    }
    
    // Start all modules
    for (const module of this.modules) {
      try {
        if (typeof module.instance.start === 'function') {
          await module.instance.start();
          console.log(`Started ${module.name} module`);
        }
      } catch (error) {
        console.error(`Error starting ${module.name}:`, error.message);
      }
    }
    
    this.running = true;
    console.log('Observer Core running. Ready to observe.');
    return true;
  }

  // Stop observation
  async stop() {
    if (!this.running) return true;
    
    console.log('Stopping Fear of Commitment Observer Core...');
    
    // Stop all modules
    for (const module of this.modules) {
      try {
        if (typeof module.instance.stop === 'function') {
          await module.instance.stop();
          console.log(`Stopped ${module.name} module`);
        }
      } catch (error) {
        console.error(`Error stopping ${module.name}:`, error.message);
      }
    }
    
    this.running = false;
    console.log('Observer Core stopped.');
    return true;
  }

  // Generate report
  generateReport() {
    if (!this.running) {
      console.error('Cannot generate report: Observer Core not running');
      return null;
    }
    
    const endTime = new Date();
    const durationMs = endTime - this.startTime;
    const durationSec = durationMs / 1000;
    
    return {
      generatedAt: endTime,
      observationPeriod: {
        start: this.startTime,
        end: endTime,
        durationSec
      },
      activeModules: this.modules.map(m => m.name),
      totalEvents: this.events.length,
      events: [...this.events] // Return copy to prevent external modification
    };
  }
}

// Export singleton instance
const observer = new ObserverCore();
module.exports = observer;

// Handle process signals for clean shutdown
process.on('SIGINT', async () => {
  console.log('\nReceived SIGINT, shutting down...');
  await observer.stop();
  process.exit(0);
});

process.on('SIGTERM', async () => {
  console.log('\nReceived SIGTERM, shutting down...');
  await observer.stop();
  process.exit(0);
});
