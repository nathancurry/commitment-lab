// Simple test to check if modules load

const observer = require('../src/index');

async function simpleTest() {
  console.log('Loading observer...');
  console.log('Observer type:', typeof observer);
  
  console.log('Starting observer...');
  const started = await observer.start();
  console.log('Started:', started);
  console.log('Observer running:', observer.running);
  console.log('Modules loaded:', observer.modules.length);
  
  console.log('\nModules:');
  observer.modules.forEach(m => {
    console.log(`- ${m.name}: ${m.instance.constructor.name}`);
  });
  
  await observer.stop();
  console.log('Test complete!');
}

simpleTest().catch(console.error);
