// Fear of Commitment - Git Monitor
// Observes Git operations and repository state

const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

class GitMonitor {
  constructor(dispatch) {
    this.dispatch = dispatch;
    this.watchInterval = 30000; // 30 seconds
    this.watchTimer = null;
    this.repos = [
      '/workspace/commitment',
      '/workspace/commitment-lab'
    ];
  }

  // Start monitoring
  start() {
    console.log('Git Monitor: Starting observation');
    
    // Initial scan
    this.scanRepositories();
    
    // Set up periodic watching
    this.watchTimer = setInterval(
      this.scanRepositories.bind(this),
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
    console.log('Git Monitor: Stopped observation');
    return true;
  }

  // Scan all repositories for changes
  scanRepositories() {
    this.dispatch({
      module: 'git',
      event: 'scan_start',
      message: 'Scanning repositories for Git activity'
    });
    
    let scanCount = 0;
    
    this.repos.forEach((repoPath, index) => {
      setTimeout(() => {
        this.scanRepository(repoPath, index === this.repos.length - 1);
      }, index * 1000); // Stagger scans
    });
  }

  // Scan a single repository
  scanRepository(repoPath, isLast) {
    fs.access(repoPath, fs.constants.F_OK, (err) => {
      if (err) {
        this.dispatch({
          module: 'git',
          event: 'repo_missing',
          path: repoPath,
          message: `Repository not found: ${repoPath}`
        });
        if (isLast) {
          this.dispatch({
            module: 'git',
            event: 'scan_complete'
          });
        }
        return;
      }
      
      const gitDir = path.join(repoPath, '.git');
      fs.access(gitDir, fs.constants.F_OK, (err) => {
        if (err) {
          this.dispatch({
            module: 'git',
            event: 'not_a_repo',
            path: repoPath,
            message: `Not a Git repository: ${repoPath}`
          });
          if (isLast) {
            this.dispatch({
              module: 'git',
              event: 'scan_complete'
            });
          }
          return;
        }
        
        // Get repository status
        this.getStatus(repoPath, isLast);
      });
    });
  }

  // Get status of a repository
  getStatus(repoPath, isLast) {
    const gitStatus = spawn('git', ['-C', repoPath, 'status', '--porcelain']);
    
    let output = '';
    gitStatus.stdout.on('data', (data) => {
      output += data.toString();
    });
    
    gitStatus.stderr.on('data', (data) => {
      console.error('Git status error:', data.toString());
    });
    
    gitStatus.on('close', (code) => {
      if (code === 0) {
        const statusLines = output.trim().split('\n').filter(Boolean);
        
        this.dispatch({
          module: 'git',
          event: 'status_check',
          path: repoPath,
          modifiedCount: statusLines.length,
          message: `Repository ${path.basename(repoPath)} has ${statusLines.length} changed files`
        });
        
        // Get last commit
        this.getLastCommit(repoPath, isLast);
      } else {
        this.dispatch({
          module: 'git',
          event: 'status_error',
          path: repoPath,
          code,
          message: `Git status failed for ${repoPath}`
        });
        if (isLast) {
          this.dispatch({
            module: 'git',
            event: 'scan_complete'
          });
        }
      }
    });
  }

  // Get last commit information
  getLastCommit(repoPath, isLast) {
    const gitLog = spawn('git', ['-C', repoPath, 'log', '-1', '--pretty=%H %s %an']);
    
    let output = '';
    gitLog.stdout.on('data', (data) => {
      output += data.toString();
    });
    
    gitLog.stderr.on('data', (data) => {
      console.error('Git log error:', data.toString());
    });
    
    gitLog.on('close', (code) => {
      if (code === 0) {
        const parts = output.trim().split(' ');
        const commitHash = parts[0] || 'unknown';
        const commitMessage = parts.slice(1).join(' ') || 'no message';
        
        this.dispatch({
          module: 'git',
          event: 'last_commit',
          path: repoPath,
          hash: commitHash,
          message: commitMessage,
          fullInfo: output.trim()
        });
      }
      
      if (isLast) {
        this.dispatch({
          module: 'git',
          event: 'scan_complete'
        });
      }
    });
  }
}

module.exports = GitMonitor;
