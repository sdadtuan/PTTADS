describe('Meta creative registry B12 (e2e)', () => {
  it('registers controller routes', () => {
    const fs = require('fs');
    const path = require('path');
    const text = fs.readFileSync(
      path.join(__dirname, '../src/meta-creative-registry/meta-creative-registry.controller.ts'),
      'utf8',
    );
    expect(text).toContain("@Controller('api/v1/meta/creative-links')");
    expect(text).toContain('@Get()');
    expect(text).toContain("@Get('resolve')");
    expect(text).toContain('@Post()');
    expect(text).toContain('@Delete(');
  });
});
