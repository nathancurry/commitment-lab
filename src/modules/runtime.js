// Fear of Commitment - Runtime Monitor
// Observes Commitment process activity

const { spawn } = require('child_process');
const psTree = require('ps-tree');

const COMMITMENT_PROCESS_NAME = 'commitment';
const COMMITMENT_PROCESS_PATH = '/workspace/commitment';

class RuntimeMonitor {
  constructor(dispatch) {
    this.dispatch = dispatch;
    this.watchInterval = 5000; // 5 seconds
    this.watchTimer = null;
    this.observedPids = new Set();
  }

  // Start monitoring
  start() {
    console.log('Runtime Monitor: Starting observation');
    
    // Initial scan
    this.scanForCommitmentProcesses();
    
    // Set up periodic watching
    this.watchTimer = setInterval(
      this.scanForCommitmentProcesses.bind(this),
      this.watchInterval
    );
    
    return true;
  }

  // Stop monitoring
  stop() {
    if (this.watchTimer) {
      clearInterval(this.watchTimer);
      this.watchTimer = null;
    }
    console.log('Runtime Monitor: Stopped observation');
    return true;
  }

  // Scan for Commitment processes
  scanForCommitmentProcesses() {
    this.dispatch({
      module: 'runtime',
      event: 'scan_start',
      message: 'Scanning for Commitment processes'
    });

    // Use pgrep to find processes containing 'commitment'
    const pgrep = spawn('pgrep', ['-f', COMMITMENT_PROCESS_NAME]);
    
    let output = '';
    pgrep.stdout.on('data', (data) => {
      output += data.toString();
    });
    
    pgrep.stderr.on('data', (data) => {
      console.error('pgrep error:', data.toString());
    });
    
    pgrep.on('close', (code) => {
      if (code === 0) {
        const pidStrings = output.trim().split('\n').filter(Boolean);
        const newPids = new Set(pidStrings.map(pid => parseInt(pid, 10)));
        
        // Track new processes
        newPids.forEach(pid => {
          if (!this.observedPids.has(pid)) {
            this.observedPids.add(pid);
            this.dispatch({
              module: 'runtime',
              event: 'process_found',
              pid,
              message: `Found Commitment process with PID ${pid}`
            });
          }
        });
        
        // Remove terminated processes
        Array.from(this.observedPids).forEach(pid => {
          if (!newPids.has(pid)) {
            this.observedPids.delete(pid);
            this.dispatch({
              module: 'runtime',
              event: 'process_terminated',
              pid,
              message: `Commitment process with PID ${pid} terminated`
            });
          }
        });
      }
      
      this.dispatch({
        module: 'runtime',
        event: 'scan_complete',
        activeProcessCount: this.observedPids.size
      });
    });
  }

  // Get process tree information
  async getProcessTree(pid) {
    return new Promise((resolve, reject) => {
      psTree(pid, (err, children) => {
        if (err) {
          reject(err);
          return;
        }
        resolve(children);
      });
    });
  }
}

module.exports = RuntimeMonitor;
