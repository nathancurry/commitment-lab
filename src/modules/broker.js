// Fear of Commitment - Broker Monitor
// Observes secret broker and credential usage

const fs = require('fs');
const path = require('path');

class BrokerMonitor {
  constructor(dispatch) {
    this.dispatch = dispatch;
    this.watchInterval = 60000; // 60 seconds
    this.watchTimer = null;
    this.brokerPaths = [
      '/workspace/commitment/broker',
      '/workspace/commitment/secret-broker',
      '/workspace/commitment/bin/secret-broker'
    ];
  }

  // Start monitoring
  start() {
    console.log('Broker Monitor: Starting observation');
    
    // Initial scan
    this.scanForBrokers();
    
    // Set up periodic watching
    this.watchTimer = setInterval(
      this.scanForBrokers.bind(this),
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
    console.log('Broker Monitor: Stopped observation');
    return true;
  }

  // Scan for broker executables
  scanForBrokers() {
    this.dispatch({
      module: 'broker',
      event: 'scan_start',
      message: 'Scanning for secret brokers'
    });
    
    let foundCount = 0;
    
    this.brokerPaths.forEach((brokerPath, index) => {
      setTimeout(() => {
        this.checkBrokerPath(brokerPath, this.brokerPaths.length - 1 === index);
      }, index * 100);
    });
  }

  // Check if a broker exists at a path
  checkBrokerPath(brokerPath, isLast) {
    fs.exists(brokerPath, (exists) => {
      if (exists) {
        fs.stat(brokerPath, (err, stat) => {
          if (!err) {
            if (stat.isFile()) {
              this.dispatch({
                module: 'broker',
                event: 'broker_found',
                path: brokerPath,
                size: stat.size,
                mtime: stat.mtime.getTime(),
                message: `Secret broker found at ${brokerPath}`
              });
            } else if (stat.isDirectory()) {
              this.dispatch({
                module: 'broker',
                event: 'broker_directory',
                path: brokerPath,
                message: `Secret broker directory at ${brokerPath}`
              });
            }
          }
        });
      }
      
      if (isLast) {
        this.dispatch({
          module: 'broker',
          event: 'scan_complete',
          foundCount
        });
      }
    });
  }

  // Check for broker process
  checkBrokerProcess() {
    // This would use process listing to find running brokers
    // Simplified for now
    this.dispatch({
      module: 'broker',
      event: 'process_check',
      message: 'Broker process monitoring not fully implemented'
    });
  }
}

module.exports = BrokerMonitor;
