// Change -> source transfer -> guest build -> activation -> visible verification.
// Build commands execute ONLY in the isolated guest. Evidence stays in BMOS_LAB.
import {mkdir, readFile, statfs} from 'node:fs/promises';
import {resolve, join} from 'node:path';
import {createHash} from 'node:crypto';
const began=performance.now();
const lab=process.env.BMOS_LAB;
if (!lab) throw Error('Set BMOS_LAB to the private lab directory');
const root=resolve(lab), here=import.meta.dir;
const recipePath=process.argv[2];
if (!recipePath) throw Error('Usage: BMOS_LAB=/private/lab bun bmos.ts recipe.json');
const recipe=await Bun.file(resolve(recipePath)).json();
if (!/^[a-z][a-z0-9-]*$/.test(recipe.name)) throw Error('Invalid recipe name');
const id=`${Date.now()}-${recipe.name}`, out=join(root,'artifacts','bmos-results',id);
await mkdir(out,{recursive:true,mode:0o700});
const quote=(s:string)=>"'"+s.replaceAll("'","'\\''")+"'";
const stages:any[]=[];let failure:string|null=null, sourceDigest:string|null=null;
const env={...process.env,BMOS_LAB:root};
async function run(argv:string[], input?:Uint8Array):Promise<string> {
  const p=Bun.spawn(argv,{env,stdin:input?new Response(input):'ignore',stdout:'pipe',stderr:'pipe'});
  const [stdout,stderr,status]=await Promise.all([new Response(p.stdout).text(),new Response(p.stderr).text(),p.exited]);
  await Bun.write(join(out,`${stages.length}-${argv[0].split('/').pop()}.log`),stdout+stderr);
  if(status)throw Error(`${argv[0]} exited ${status}`);
  return stdout;
}
async function stage(name:string, action:()=>Promise<any>) {
  const t=performance.now();const item:any={name};stages.push(item);
  try {const result=await action();item.passed=true;return result;}
  catch(e){item.passed=false;throw e;}
  finally {item.seconds=(performance.now()-t)/1000;console.log(`${name}: ${item.seconds.toFixed(3)}s`);}
}
const guest=(command:string,input?:Uint8Array)=>run(['bash',join(root,'candidates/terminal-fast/guest.sh'),command],input);
try {
  await stage('preflight',async()=>{
    const disk=await statfs(root);if(disk.bavail*disk.bsize<100.5*1024**3)throw Error('Preserve host disk reserve');
    const active=Bun.spawnSync(['systemctl','--user','is-active','os-evolution-terminal'],{stdout:'pipe'}).exitCode===0;
    if(!active){await run(['bash',join(root,'candidates/terminal-fast/start.sh'),'gpu']);await run(['python',join(root,'candidates/terminal-fast/ready.py')]);}
    await run(['python',join(root,'candidates/terminal-fast/check-isolation.py')]);
    await guest('test "$(cat /etc/os-evolution-guest)" = arch-baseline');
  });
  if(recipe.source){
    sourceDigest=await stage('source-sync',()=>run(['python',join(here,'tools/sync-source.py'),resolve(root,recipe.source),recipe.name]));
    sourceDigest=sourceDigest.trim();
  }
  const cwd=`/home/matt/bmos-build/${recipe.name}/src`;
  const inSource=(command:string)=>`set -eu; cd ${quote(cwd)}; export MAKEFLAGS=-j2 CMAKE_BUILD_PARALLEL_LEVEL=2 CARGO_BUILD_JOBS=2; ${command}`;
  await stage('build',()=>guest(inSource(recipe.build)));
  await stage('deploy',()=>guest(inSource(recipe.deploy)));
  if(recipe.restart==='desktop')await stage('activate',async()=>{
    await guest('systemctl --user stop terminal-fast-desktop.service; tmux kill-server; systemctl --user start terminal-fast-desktop.service');
    await run(['python',join(root,'candidates/terminal-fast/ready.py')]);
  });
  if(recipe.restart==='reboot')await stage('reboot',async()=>{
    await run(['python',join(root,'candidates/terminal-fast/qmp.py'),'system_powerdown']);
    for(let i=0;i<150;i++){
      if(Bun.spawnSync(['systemctl','--user','is-active','os-evolution-terminal'],{stdout:'ignore'}).exitCode!==0)break;
      await Bun.sleep(200);
    }
    await run(['bash',join(root,'candidates/terminal-fast/start.sh'),'gpu']);
    await run(['python',join(root,'candidates/terminal-fast/ready.py')]);
  });
  await stage('verify-live-artifact',()=>guest(inSource(recipe.verify)));
  await stage('graphical-suite',()=>run(['python',join(here,'evaluator/profile-suite.py')]));
} catch(e) {failure=String(e);console.error(failure);}
const seconds=(performance.now()-began)/1000;
const report={id,recipe:recipe.name,sourceDigest,stages,totalChangeToVerificationSeconds:seconds,budgetSeconds:20,budgetMet:seconds<=20,functionalPass:failure===null,failure,pass:failure===null&&seconds<=20};
await Bun.write(join(out,'result.json'),JSON.stringify(report,null,2));
console.log(JSON.stringify(report,null,2));console.log(out);
process.exit(report.pass?0:1);
