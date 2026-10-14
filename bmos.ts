// Change -> source transfer -> guest build -> activation -> visible verification.
// Build commands execute ONLY in the isolated guest. Evidence stays in BMOS_LAB.
import {mkdir, readFile, statfs} from 'node:fs/promises';
import {resolve, join} from 'node:path';
import {createHash} from 'node:crypto';
const startedNS=process.hrtime.bigint(), began=performance.now();
const lab=process.env.BMOS_LAB;
if (!lab) throw Error('Set BMOS_LAB to the private lab directory');
const root=resolve(lab), here=import.meta.dir;
const recipePath=process.argv[2];
if (!recipePath) throw Error('Usage: BMOS_LAB=/private/lab bun bmos.ts recipe.json');
const recipeBytes=await Bun.file(resolve(recipePath)).text();
const recipe=JSON.parse(recipeBytes);
const recipeSha256=createHash('sha256').update(recipeBytes).digest('hex');
const evaluatorSha256=createHash('sha256');
for(const path of ['bmos.ts','evaluator/visual-suite.py','evaluator/qmp.py','evaluator/framebuffer.py','evaluator/profile-suite.py','vm/start.sh','vm/launch.sh','vm/inside-sandbox.sh','vm/guest.sh','vm/check-isolation.py','vm/ready.py'])evaluatorSha256.update(path).update(new Uint8Array(await Bun.file(join(here,path)).arrayBuffer()));
const implementationSha256=evaluatorSha256.digest('hex');
if (!/^[a-z][a-z0-9-]*$/.test(recipe.name)) throw Error('Invalid recipe name');
const id=`${Date.now()}-${recipe.name}`, out=join(root,'artifacts','bmos-results',id);
const quote=(s:string)=>"'"+s.replaceAll("'","'\\''")+"'";
let calls=0;
const stages:any[]=[];let failure:string|null=null, sourceDigest:string|null=null;
const env={...process.env,BMOS_LAB:root};
if(!process.env.BMOS_LOCKED){
  const p=Bun.spawn(['flock','-n','-E','73',join(root,'runtime/bmos-pipeline.lock'),'bun',import.meta.path,...process.argv.slice(2)],{env:{...env,BMOS_LOCKED:'1',BMOS_STARTED_NS:startedNS.toString()},stdin:'inherit',stdout:'inherit',stderr:'inherit'});
  const status=await p.exited;
  if(status===73)console.error('Another build/verification run is active.');
  process.exit(status);
}
await mkdir(out,{recursive:true,mode:0o700});
async function run(argv:string[], input?:Uint8Array, accepted=[0]):Promise<string> {
  const p=Bun.spawn(argv,{env,stdin:input?new Response(input):'ignore',stdout:'pipe',stderr:'pipe'});
  const [stdout,stderr,status]=await Promise.all([new Response(p.stdout).text(),new Response(p.stderr).text(),p.exited]);
  await Bun.write(join(out,`${++calls}-${argv[0].split('/').pop()}.log`),stdout+stderr);
  if(!accepted.includes(status))throw Error(`${argv[0]} exited ${status}`);
  return stdout;
}
async function stage(name:string, action:()=>Promise<any>) {
  const t=performance.now();const item:any={name};stages.push(item);
  try {const result=await action();item.passed=true;return result;}
  catch(e){item.passed=false;throw e;}
  finally {item.seconds=(performance.now()-t)/1000;console.log(`${name}: ${item.seconds.toFixed(3)}s`);}
}
const guest=(command:string,input?:Uint8Array)=>run(['bash',join(here,'vm/guest.sh'),command],input);
try {
  await stage('preflight',async()=>{
    const disk=await statfs(root);if(disk.bavail*disk.bsize<100.5*1024**3)throw Error('Preserve host disk reserve');
    const active=Bun.spawnSync(['systemctl','--user','is-active','os-evolution-terminal'],{stdout:'pipe'}).exitCode===0;
    if(!active){await run(['bash',join(here,'vm/start.sh'),'gpu']);await run(['python',join(here,'vm/ready.py')]);}
    await run(['python',join(here,'vm/check-isolation.py')]);
    await guest('test "$(cat /etc/os-evolution-guest)" = arch-baseline; if tmux -L bmos-daily has-session 2>/dev/null; then echo "Close and save the daily session before destructive build verification" >&2; exit 70; fi; systemctl --user stop bmos-daily-desktop.service; systemctl --user start terminal-model.service');
    if(Bun.spawnSync(['systemctl','--user','is-active','--quiet','bmos-viewer']).exitCode===0)await run(['systemctl','--user','stop','bmos-viewer']);
  });
  if(recipe.source){
    sourceDigest=await stage('source-sync',()=>run(['python',join(here,'tools/sync-source.py'),resolve(root,recipe.source),recipe.name]));
    sourceDigest=sourceDigest.trim();
  }
  const cwd=`/home/matt/bmos-build/${recipe.name}/src`;
  if(recipe.guestSource)sourceDigest=await stage('guest-source-identity',()=>guest(`cd ${quote(cwd)}; test -z "$(git ls-files --others --exclude-standard)"; (git rev-parse HEAD; git diff --binary HEAD; sha256sum .config) | sha256sum`));
  const inSource=(command:string)=>`set -eu; cd ${quote(cwd)}; export MAKEFLAGS=-j2 CMAKE_BUILD_PARALLEL_LEVEL=2 CARGO_BUILD_JOBS=2; ${command}`;
  await stage('build',()=>guest(inSource(recipe.build)));
  await stage('deploy',()=>guest(inSource(recipe.deploy)));
  if(recipe.restart==='desktop')await stage('activate',async()=>{
    await guest('systemctl --user stop terminal-fast-desktop.service; tmux kill-server; systemctl --user start terminal-fast-desktop.service');
    await run(['python',join(here,'vm/ready.py')]);
  });
  if(recipe.restart==='reboot')await stage('reboot',async()=>{
    await guest('sudo systemctl stop evolution-desktop.service; sudo systemctl poweroff --no-block');
    for(let i=0;i<150;i++){
      if(Bun.spawnSync(['systemctl','--user','is-active','os-evolution-terminal'],{stdout:'ignore'}).exitCode!==0)break;
      await Bun.sleep(200);
    }
    if(Bun.spawnSync(['systemctl','--user','is-active','--quiet','os-evolution-terminal']).exitCode===0)throw Error('Guest did not complete a clean shutdown');
    await run(['bash',join(here,'vm/start.sh'),'gpu']);
    await run(['python',join(here,'vm/ready.py')]);
  });
  await stage('verify-live-artifact',()=>guest(inSource(recipe.verify)));
  await stage('graphical-suite',async()=>{
    const output=await run(['python',join(here,'evaluator/profile-suite.py')],undefined,[0,1]);
    const profilePath=output.split('\n').find(line=>line.startsWith(root+'/')&&/\/profile-\d+\.json$/.test(line));
    if(!profilePath)throw Error('Graphical evaluator did not produce a report');
    const profile=await Bun.file(profilePath).json();
    const runPath=profile.stdout.split('\n').find((line:string)=>line.startsWith(root+'/')&&line.includes('/evidence/run-/'));
    if(!runPath)throw Error('Missing graphical run');
    const report=await Bun.file(join(runPath,'results.json')).json();
    const contract=await Bun.file(join(root,'candidates/terminal-fast/references/REVIEWED.json')).json();
    if(report.failedStep||!report.functionalPass||report.calibration||JSON.stringify(report.results.map((r:any)=>r.name))!==JSON.stringify(contract.references.map((r:any)=>r.name))||report.results.some((r:any)=>!r.state||r.visual!==true))throw Error('Graphical functional contract failed: '+report.failure);
    stages.at(-1).evidence=runPath;
    stages.at(-1).suiteSeconds=profile.wallSeconds;
  });
} catch(e) {failure=String(e);console.error(failure);}
const seconds=process.env.BMOS_STARTED_NS?Number(process.hrtime.bigint()-BigInt(process.env.BMOS_STARTED_NS))/1e9:(performance.now()-began)/1000;
const report={id,recipe:recipe.name,recipeSha256,implementationSha256,sourceDigest,stages,totalChangeToVerificationSeconds:seconds,budgetSeconds:20,budgetMet:seconds<=20,functionalPass:failure===null,failure,pass:failure===null&&seconds<=20};
await Bun.write(join(out,'result.json'),JSON.stringify(report,null,2));
console.log(JSON.stringify(report,null,2));console.log(out);
process.exit(report.pass?0:1);
