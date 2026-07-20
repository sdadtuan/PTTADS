import { checkHtmlLinks, extractHtmlLinks, runCampaignPreflight, runTemplatePreflight } from './email-marketing-preflight.util';

describe('email-marketing-preflight.util', () => {
  it('passes template with subject, body, and unsubscribe', () => {
    const out = runTemplatePreflight({
      subject: 'Hello world',
      htmlBody: '<p>Content here</p><a href="{{unsubscribe_url}}">Unsubscribe</a>',
    });
    expect(out.passed).toBe(true);
    expect(out.checks.some((c) => c.id === 'unsubscribe' && c.status === 'pass')).toBe(true);
    expect(out.checks.some((c) => c.id === 'list_unsubscribe_header' && c.status === 'pass')).toBe(true);
  });

  it('fails template without unsubscribe link', () => {
    const out = runTemplatePreflight({
      subject: 'Hello',
      htmlBody: '<p>Content without opt-out</p>',
    });
    expect(out.passed).toBe(false);
  });

  it('flags broken javascript links', () => {
    const html = '<a href="javascript:alert(1)">bad</a><a href="{{unsubscribe_url}}">Unsub</a>';
    const links = extractHtmlLinks(html);
    expect(links).toHaveLength(2);
    const broken = checkHtmlLinks(links);
    expect(broken.bad.length).toBe(1);
    const out = runTemplatePreflight({ subject: 'Hi there', htmlBody: html });
    expect(out.checks.find((c) => c.id === 'broken_links')?.status).toBe('fail');
  });

  it('passes valid http links', () => {
    const html =
      '<a href="https://example.com/page">CTA</a><a href="{{unsubscribe_url}}">Unsub</a>';
    const out = runTemplatePreflight({ subject: 'Hello world', htmlBody: html });
    expect(out.checks.find((c) => c.id === 'broken_links')?.status).toBe('pass');
  });

  it('warns domain auth when domain not registered', () => {
    const out = runTemplatePreflight({
      subject: 'Hello world',
      htmlBody: '<p>Hi</p><a href="{{unsubscribe_url}}">Unsub</a>',
      fromEmail: 'noreply@client.com',
    });
    expect(out.checks.find((c) => c.id === 'domain_auth')?.status).toBe('warn');
  });

  it('passes domain auth when SPF/DKIM pass', () => {
    const out = runTemplatePreflight({
      subject: 'Hello world',
      htmlBody: '<p>Hi</p><a href="{{unsubscribe_url}}">Unsub</a>',
      fromEmail: 'noreply@client.com',
      domainAuth: { spfStatus: 'pass', dkimStatus: 'pass' },
    });
    expect(out.checks.find((c) => c.id === 'domain_auth')?.status).toBe('pass');
  });

  it('fails campaign preflight when audience is empty', () => {
    const templateChecks = runTemplatePreflight({
      subject: 'Hello',
      htmlBody: '<p>Hi</p><a href="{{unsubscribe_url}}">Unsubscribe</a>',
    });
    const out = runCampaignPreflight({
      templateChecks,
      audienceCount: 0,
      segmentName: 'Test segment',
    });
    expect(out.passed).toBe(false);
    expect(out.checks.some((c) => c.id === 'audience' && c.status === 'fail')).toBe(true);
  });
});
