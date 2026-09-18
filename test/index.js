// Basic test for Fear of Commitment components

const observer = require('../src/index');

async function runTest() {
  console.log('Running Fear of Commitment component tests...\n');
  
  // Test 1: Start observer
  console.log('Test 1: Starting observer core...');
  const started = await observer.start();
  console.log(`Observer started: ${started}`);
  
  if (!started) {
    console.error('Failed to start observer');
    process.exit(1);
  }
  
  // Wait a bit for modules to load and scan
  await new Promise(resolve => setTimeout(resolve, 7000));
  
  // Test 2: Generate report
  console.log('\nTest 2: Generating report...');
  const report = observer.generateReport();
  
  if (report) {
    console.log('Generated report:');
    console.log(`- Observation period: ${report.observationPeriod.durationSec.toFixed(2)} seconds`);
    console.log(`- Active modules: ${report.activeModules.join(', ')}`);
    console.log(`- Total events: ${report.totalEvents}`);
  }
  
  // Test 3: Check events
  console.log('\nTest 3: Recent events:');
  if (report && report.events.length > 0) {
    const recentEvents = report.events.slice(-5);
    recentEvents.forEach((event, i) => {
      console.log(`${i + 1}. ${event.module}:${event.event} - ${event.message || JSON.stringify(event)}`);
    });
  }
  
  // Test 4: Stop observer
  console.log('\nTest 4: Stopping observer...');
  const stopped = await observer.stop();
  console.log(`Observer stopped: ${stopped}`);
  
  console.log('\nAll tests completed successfully!');
  process.exit(0);
}

runTest().catch(error => {
  console.error('Test failed:', error);
  process.exit(1);
});
