// Fear of Commitment - Container Monitor
// Observes Docker/Podman container activity

const { spawn } = require('child_process');

class ContainerMonitor {
  constructor(dispatch) {
    this.dispatch = dispatch;
    this.watchInterval = 10000; // 10 seconds
    this.watchTimer = null;
    this.containerRegistry = new Map(); // pid -> container info
  }

  // Start monitoring
  start() {
    console.log('Container Monitor: Starting observation');
    
    // Initial scan
    this.scanForContainers();
    
    // Set up periodic watching
    this.watchTimer = setInterval(
      this.scanForContainers.bind(this),
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
    console.log('Container Monitor: Stopped observation');
    return true;
  }

  // Scan for containers
  scanForContainers() {
    this.dispatch({
      module: 'containers',
      event: 'scan_start',
      message: 'Scanning for containers'
    });
    
    // Try Docker first
    this.scanWithTool('docker', 'Docker');
    
    // If no Docker, try Podman
    setTimeout(() => {
      this.scanWithTool('podman', 'Podman');
    }, 100);
  }

  // Scan for containers using a specific tool
  scanWithTool(toolName, displayName) {
    try {
      const psCommand = spawn(toolName, ['ps', '--format', '{{.ID}}', '--format', '{{.Names}}', '--format', '{{.Status}}', '--format', '{{.Command}}']);
      
      let output = '';
      psCommand.stdout.on('data', (data) => {
        output += data.toString();
      });
      
      psCommand.stderr.on('data', (data) => {
        // Tool not installed - ignore
      });
      
      psCommand.on('close', (code) => {
        if (code === 0) {
          const lines = output.trim().split('\n').filter(Boolean);
          if (lines.length > 1) {
            // Lines[0] contains column headers, skip it
            const activeContainers = lines.slice(1);
            
            this.dispatch({
              module: 'containers',
              event: 'containers_found',
              tool: displayName,
              count: activeContainers.length
            });
            
            // Collect basic info for each container
            const containerIds = activeContainers.map(line => {
              const parts = line.split(' ').filter(Boolean);
              return parts[0] || 'unknown';
            }).filter(id => id !== 'unknown');
            
            if (containerIds.length > 0) {
              this.dispatch({
                module: 'containers',
                event: 'container_list',
                tool: displayName,
                containerIds
              });
            }
          }
        } else {
          // Tool not available, that's okay
        }
      });
    } catch (error) {
      // Tool not installed - that's okay, we'll try the next one
      this.dispatch({
        module: 'containers',
        event: 'tool_unavailable',
        tool: displayName,
        message: `${displayName} not installed`
      });
    }
  }

  // Get detailed info for a specific container
  async getContainerDetails(tool, containerId) {
    return new Promise((resolve, reject) => {
      const inspect = spawn(tool, ['inspect', containerId]);
      
      let output = '';
      inspect.stdout.on('data', (data) => {
        output += data.toString();
      });
      
      inspect.stderr.on('data', (data) => {
        console.error(`Error inspecting container ${containerId}:`, data.toString());
      });
      
      inspect.on('close', (code) => {
        if (code === 0) {
          try {
            const details = JSON.parse(output);
            resolve(details);
          } catch (e) {
            reject(new Error('Failed to parse container details'));
          }
        } else {
          reject(new Error(`Container inspection failed with code ${code}`));
        }
      });
    });
  }
}

module.exports = ContainerMonitor;
