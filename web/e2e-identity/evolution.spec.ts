import { test, expect, type Page } from './authenticated';

async function mutate(page:Page,path:string,data:unknown,method='POST') {
  const csrf=await (await page.request.get('/api/v1/auth/csrf')).json();
  const response=await page.request.fetch('/api/v1'+path,{method,data,headers:{'X-CSRF-Token':csrf.csrf_token,'Idempotency-Key':crypto.randomUUID()}});
  expect(response.ok(),await response.text()).toBeTruthy();return response.json();
}
async function panel(page:Page) {
  await page.goto('/');
  await page.getByRole('group',{name:'Ações principais'}).getByRole('button',{name:'Abrir atendimento',exact:true}).click();
  return page.getByRole('region',{name:'Painel de atendimentos',exact:true});
}

test('ciclo interno na web preserva ID, atualizações e validação independente',async({page},info)=>{
  if(info.project.name==='mobile-web')await page.setViewportSize({width:360,height:800});
  const area=await panel(page);
  await area.getByLabel('Atividade interna',{exact:true}).check();
  await area.getByLabel('Descrição do atendimento ou atualização').fill('Relato interno fictício '+crypto.randomUUID());
  const response=page.waitForResponse(r=>r.url().endsWith('/api/v1/attendances')&&r.request().method()==='POST');
  await area.getByRole('button',{name:'Salvar atendimento',exact:true}).click();
  const opened=await (await response).json();
  await expect(area.getByLabel('Ação no atendimento')).toBeVisible();
  await area.getByLabel('Descrição do atendimento ou atualização').fill('Atualização fictícia preservada');
  await area.getByLabel('Próxima ação',{exact:true}).fill('Conferir retorno fictício');
  const updated=page.waitForResponse(r=>r.url().endsWith(`/attendances/${opened.id}/updates`)&&r.request().method()==='POST');
  await area.getByRole('button',{name:'Salvar atendimento',exact:true}).click();
  const update=await (await updated).json();
  await expect(area.getByRole('button',{name:'Salvar atendimento',exact:true})).toBeEnabled();
  await expect(area.locator('.workspace-detail').getByText('Atualização fictícia preservada',{exact:true}).first()).toBeVisible();
  const validation=area.getByRole('region',{name:'Fidelidade do texto',exact:true}).last();
  await expect(validation.getByRole('button',{name:'Validar agora',exact:true})).toBeDisabled();
  await validation.getByRole('button',{name:'Validar depois',exact:true}).click();
  await expect(validation.getByRole('status')).toContainText('pode validar depois');
  await validation.getByLabel('Conferi esta versão exata do texto').check();
  await validation.getByRole('button',{name:'Validar agora',exact:true}).click();
  await expect(validation.getByRole('heading')).toHaveText('Fidelidade do texto: Validado');
  expect((await (await page.request.get(`/api/v1/attendances/${opened.id}`)).json()).status).toBe('em_andamento');
  const fresh=await (await page.request.get(`/api/v1/records/${update.update.id}`)).json();
  await mutate(page,`/records/${fresh.id}`,{revision:fresh.revision,texto_organizado:'Correção humana fictícia'},'PATCH');
  await expect(validation.getByRole('heading')).toHaveText('Fidelidade do texto: Não validado',{timeout:10000});
  await validation.getByText('Histórico de validações',{exact:true}).click();
  await expect(validation.getByText(/Validado por:/)).toHaveCount(1);
  await area.getByLabel('Ação no atendimento').selectOption('finalizar');
  await area.getByLabel('Descrição do atendimento ou atualização').fill('Conclusão fictícia relatada');
  await area.getByLabel('Resultado da finalização').fill('Retorno realizado');
  await area.getByRole('button',{name:'Salvar atendimento',exact:true}).click();
  await expect(area.getByLabel('Ação no atendimento')).toHaveCount(0);
  const final=await (await page.request.get(`/api/v1/attendances/${opened.id}`)).json();
  expect(final.status).toBe('finalizado');expect(final.id).toBe(opened.id);expect(final.updates_total).toBe(2);
  expect(final.record.ocorrido_em).toBe(opened.record.ocorrido_em);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();
});

test('resposta perdida mantém o registro salvo e reenvia a mesma chave',async({page})=>{
  const area=await panel(page);
  await area.getByLabel('Atividade interna',{exact:true}).check();
  const text='Idempotência fictícia '+crypto.randomUUID();
  await area.getByLabel('Descrição do atendimento ou atualização').fill(text);
  let intercepted=false;
  await page.route('**/api/v1/attendances',async route=>{
    if(route.request().method()!=='POST'||intercepted){await route.continue();return;}
    intercepted=true;const result=await route.fetch();expect(result.status()).toBe(201);await route.abort('failed');
  });
  await area.getByRole('button',{name:'Salvar atendimento',exact:true}).click();
  await expect(area.getByText('Reenvie com a mesma chave. O registro já salvo será preservado.',{exact:true})).toBeVisible();
  await area.getByRole('button',{name:'Tentar novamente',exact:true}).click();
  await expect(area.getByLabel('Ação no atendimento')).toBeVisible();
  const records=await (await page.request.get('/api/v1/attendances?mine=true&limit=100')).json();
  expect(records.items.filter((r:{record:{texto_original:string}})=>r.record.texto_original===text)).toHaveLength(1);
});

test('outro leitor valida pela fila; falha preserva original e permite tentar novamente',async({page,browser})=>{
  const client=await mutate(page,'/clients',{name:'Cliente fictício de validação '+crypto.randomUUID()});
  const record=await mutate(page,'/records',{client_id:client.id,type:'finalizacao',texto_original:'Relato fictício que será conferido por outro leitor'});
  await mutate(page,`/records/${record.id}/actions`,{revision:record.revision,action:'confirmar'});
  const email=`validacao-${crypto.randomUUID()}@example.test`;
  const invitation=await mutate(page,'/invitations',{email,role:'tecnico'});
  const context=await browser.newContext({baseURL:test.info().project.use.baseURL});
  try {
    const csrf=await (await context.request.get('/api/v1/auth/csrf')).json();
    const accepted=await context.request.post('/api/v1/invitations/accept',{data:{email,password:'Ficticio!'+crypto.randomUUID(),name:'Leitor fictício',token:invitation.invitation_path.split('=')[1]},headers:{'X-CSRF-Token':csrf.csrf_token}});
    expect(accepted.ok()).toBeTruthy();
    const tech=await context.newPage();await tech.goto('/');
    await tech.getByRole('region',{name:'Área da organização',exact:true}).getByRole('button',{name:'Atendimentos',exact:true}).click();
    const area=tech.getByRole('region',{name:'Atendimentos',exact:true});
    await area.getByRole('button',{name:'Validações pendentes',exact:true}).click();
    let failed=true;
    await tech.route(`**/api/v1/records/${record.id}/text-validation`,async route=>{if(failed)await route.abort();else await route.continue();});
    await area.getByRole('region',{name:'Validações pendentes',exact:true}).locator('article').filter({hasText:record.id}).getByRole('button',{name:'Revisar texto',exact:true}).click();
    const detail=area.locator('.workspace-detail');
    const validation=detail.getByRole('region',{name:'Fidelidade do texto',exact:true});
    await expect(validation.getByRole('heading')).toHaveText('Fidelidade do texto: Falha');
    await expect(detail.getByText('Relato original: Relato fictício que será conferido por outro leitor',{exact:true})).toBeVisible();
    failed=false;await validation.getByRole('button',{name:'Tentar novamente',exact:true}).click();
    await expect(validation.getByLabel('Conferi esta versão exata do texto')).not.toBeChecked();
    await validation.getByLabel('Conferi esta versão exata do texto').check();
    await validation.getByRole('button',{name:'Validar agora',exact:true}).click();
    await expect(validation.getByRole('heading')).toHaveText('Fidelidade do texto: Validado');
    const after=await (await page.request.get(`/api/v1/records/${record.id}`)).json();
    expect(after.status).toBe('confirmado');expect(after.ocorrido_em).toBe(record.ocorrido_em);
  } finally {await context.close();}
});
