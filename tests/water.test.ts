import test from "node:test";
import assert from "node:assert/strict";
import { serviceUrl, WaterClient, prepareComputeSession } from "../src/water/client";

test("online service requires HTTPS and rejects credentials or query tokens in URLs", () => {
  assert.equal(serviceUrl("https://example.com/nbs-api/"), "https://example.com/nbs-api");
  assert.equal(serviceUrl("http://127.0.0.1:8080/api"), "http://127.0.0.1:8080/api");
  for (const url of ["http://example.com/api", "https://user:secret@example.com/api", "https://example.com/api?token=secret", "javascript:alert(1)"]) assert.throws(() => serviceUrl(url));
});

test("job submission sends credentials only as headers and preserves retry identity", async () => {
  const original = globalThis.fetch;
  const calls: { url: string; options?: RequestInit }[] = [];
  globalThis.fetch = (async (url: string | URL | Request, options?: RequestInit) => { calls.push({url:String(url),options}); return new Response(JSON.stringify({id:"task"})); }) as typeof fetch;
  try {
    const client = new WaterClient("https://example.com/api", "private-access-code");
    const request = {mode:"sample" as const,name:"Sample",start:"2021-07-01",end:"2021-07-31",bbox:[31,28.9,31.2,29.1]};
    await client.submit(request,"same-retry-key"); await client.submit(request,"same-retry-key");
    assert.equal(calls[0].url,"https://example.com/api/jobs");
    assert.ok(!calls[0].url.includes("private-access-code"));
    assert.equal((calls[0].options?.headers as Record<string,string>).Authorization,"Bearer private-access-code");
    assert.equal((calls[0].options?.headers as Record<string,string>)["Idempotency-Key"],(calls[1].options?.headers as Record<string,string>)["Idempotency-Key"]);
  } finally { globalThis.fetch = original; }
});

test("downloads reject substituted or truncated result data", async () => {
  const original = globalThis.fetch;
  globalThis.fetch = (async () => new Response("tampered")) as typeof fetch;
  try {
    const client = new WaterClient("https://example.com/api", "code");
    await assert.rejects(() => client.asset("task", {file:"whole.tif",bytes:8,sha256:"0".repeat(64),media_type:"image/tiff"}),/checksum/);
    await assert.rejects(() => client.asset("task", {file:"../private.log",bytes:8,sha256:"0".repeat(64),media_type:"text/plain"}),/Invalid/);
  } finally { globalThis.fetch = original; }
});

test("automatic workspace requests share one bootstrap and use cookies without a code", async () => {
  const original=globalThis.fetch;
  const calls:{url:string;options?:RequestInit}[]=[];
  globalThis.fetch=(async (url,options)=>{calls.push({url:String(url),options});return new Response(JSON.stringify({ready:true}));}) as typeof fetch;
  try {
    await Promise.all([prepareComputeSession("https://example.com/api"),prepareComputeSession("https://example.com/api")]);
    assert.equal(calls.length,1);
    assert.equal(calls[0].url,"https://example.com/api/session");
    assert.equal(calls[0].options?.credentials,"include");
    assert.equal((calls[0].options?.headers as Record<string,string>).Authorization,undefined);
    await new WaterClient("https://example.com/api").jobs();
    assert.equal(calls[1].options?.credentials,"include");
    assert.equal((calls[1].options?.headers as Record<string,string>).Authorization,undefined);
  } finally {globalThis.fetch=original;}
});
