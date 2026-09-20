// Fear of Commitment - Network Monitor
// Observes network connections and metadata

const fs = require('fs');
const { spawn } = require('child_process');

class NetworkMonitor {
  constructor(dispatch) {
    this.dispatch = dispatch;
    this.watchInterval = 15000; // 15 seconds
    this.watchTimer = null;
  }

  // Start monitoring
  start() {
    console.log('Network Monitor: Starting observation');
    
    // Initial scan
    this.scanNetworkConnections();
    
    // Set up periodic watching
    this.watchTimer = setInterval(
      this.scanNetworkConnections.bind(this),
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
    console.log('Network Monitor: Stopped observation');
    return true;
  }

  // Scan network connections
  scanNetworkConnections() {
    this.dispatch({
      module: 'network',
      event: 'scan_start',
      message: 'Scanning network connections'
    });
    
    // Get network connections using ss or netstat
    this.getNetworkConnections('ss', ['-tunp']);
    
    // Fallback to netstat if ss is not available
    setTimeout(() => {
      this.getNetworkConnections('netstat', ['-tunp']);
    }, 100);
  }

  // Get network connections using a specific tool
  getNetworkConnections(tool, args) {
    try {
      const netstat = spawn(tool, args);
      
      let output = '';
      netstat.stdout.on('data', (data) => {
        output += data.toString();
      });
      
      netstat.stderr.on('data', (data) => {
        // Ignore errors if tool is not installed
      });
      
      netstat.on('close', (code) => {
        if (code === 0) {
          const lines = output.trim().split('\n');
          const connections = [];
          
          // Parse connections (simplified)
          for (let i = 1; i < lines.length; i++) {
            const line = lines[i];
            if (line && line.includes('ESTABLISHED') || line.includes('SYN_SENT') || line.includes('SYN_RECV')) {
              connections.push(line);
            }
          }
          
          this.dispatch({
            module: 'network',
            event: 'connections_found',
            tool,
            count: connections.length,
            message: `Found ${connections.length} active network connections`
          });
        }
      });
    } catch (error) {
      // Tool not installed - that's okay
      this.dispatch({
        module: 'network',
        event: 'tool_unavailable',
        tool,
        message: `${tool} not available`
      });
    }
  }

  // Get process network usage
  getProcessNetworkStats() {
    // Would use lsof or similar to get per-process network stats
    this.dispatch({
      module: 'network',
      event: 'process_stats',
      message: 'Process-level network monitoring not fully implemented'
    });
  }
}

module.exports = NetworkMonitor;
