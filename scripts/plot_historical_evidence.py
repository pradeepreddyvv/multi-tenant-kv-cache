"""Recreate the Nov 10 feasibility figures from the curated evidence pack (task C02).

Usage:
    python3 scripts/plot_historical_evidence.py EVIDENCE_DIR OUT_DIR

EVIDENCE_DIR holds the pack files from the docs/team-handoff branch
(docs/team/evidence/). OUT_DIR receives three SVG figures and figure-data.json,
the exact numbers plotted. Standard library only; no inference, no GPU.
The evidence files are only read, never modified.
"""
import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape

GIB = 2 ** 30
MIB = 2 ** 20

# Light slide surface; categorical slots 1-2 of the reference palette
# (validated: CVD dE 24.7, normal-vision dE 33.6, both >= 3:1 contrast).
SURFACE = '#fcfcfb'
INK = '#0b0b0b'
INK_2 = '#52514e'
GRID = '#e4e3df'
BLUE = '#2a78d6'
ORANGE = '#eb6834'
FONT = 'Inter, Helvetica, Arial, sans-serif'
W, H = 960, 540


# ---------------------------------------------------------------- data

def scale_points(occupancy):
    """(completed requests, retained GiB) from gpu-scale-occupancy.json."""
    points = {}
    for row in occupancy['occupancy']:
        label = row['label']
        if label == 'before_population':
            n = 0
        elif label.startswith('after_') and label[6:].isdigit():
            n = int(label[6:])
        else:
            continue  # e.g. after_retention_probes: same population, not a fill step
        points[n] = row['tensor_bytes'] / GIB
    return sorted(points.items())


def quota_series(timeline):
    """Per-sample seconds, tenant A bytes/limit and the common B/C/D bytes."""
    state = timeline[0]
    t0 = state['started_at']
    rows = []
    for sample in state['samples']:
        peers = {sample['bytes'].get(t, 0) for t in ('B', 'C', 'D')}
        if len(peers) != 1:
            raise ValueError('B, C and D differ at t=%.3f; plot them separately' % sample['time'])
        rows.append({'seconds': sample['time'] - t0,
                     'a_MiB': sample['bytes'].get('A', 0) / MIB,
                     'a_limit_MiB': sample['limits']['A'] / MIB,
                     'peer_each_MiB': peers.pop() / MIB})
    events = [{'seconds': e['applied_at'] - t0, 'tenant': e['tenant'],
               'limit_MiB': e['limit_bytes'] / MIB} for e in state['events']]
    return rows, events


def overlap_spans(rows):
    """(start s, end s, MiB) step segments where A holds exactly the peers' value."""
    spans = []
    for row, nxt in zip(rows, rows[1:]):
        if row['a_MiB'] == row['peer_each_MiB']:
            if spans and spans[-1][1] == row['seconds'] and spans[-1][2] == row['a_MiB']:
                spans[-1] = (spans[-1][0], nxt['seconds'], row['a_MiB'])
            else:
                spans.append((row['seconds'], nxt['seconds'], row['a_MiB']))
    return spans


def tenant_outcomes(first, repeat):
    """Miss/hit counts per (mode, repetition). Both fresh-process runs must agree."""
    def counts(summary):
        return [(g['mode'], g['repetition'], g['requests'], g['lookup_misses'],
                 g['actual_retrieves_768']) for g in summary['groups']]
    if counts(first) != counts(repeat):
        raise ValueError('The two tenant runs disagree; plot them separately')
    return [{'mode': m, 'repetition': r, 'requests': n, 'misses': miss, 'retrieved_768': hit}
            for m, r, n, miss, hit in counts(repeat)]


# ---------------------------------------------------------------- svg helpers

def text(x, y, s, size=13, fill=INK_2, anchor='start', weight='normal'):
    return ('<text x="%.1f" y="%.1f" font-size="%d" fill="%s" text-anchor="%s" '
            'font-weight="%s">%s</text>' % (x, y, size, fill, anchor, weight, escape(s)))


def frame(title, subtitle, caption, body):
    lines = [text(32, 40, title, 22, INK, weight='bold'), text(32, 66, subtitle, 15)]
    for i, line in enumerate(caption):
        lines.append(text(32, H - 24 - 17 * (len(caption) - 1 - i), line, 12))
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
            'viewBox="0 0 %d %d" font-family="%s" role="img" aria-label="%s">'
            '<rect width="100%%" height="100%%" fill="%s"/>%s%s</svg>\n'
            % (W, H, W, H, FONT, escape(title, {'"': '&quot;'}), SURFACE,
               ''.join(lines), ''.join(body)))


class Axes:
    """Linear axes with recessive grid; plot box in pixels."""

    def __init__(self, left, top, right, bottom, xmax, ymax, tick=13, label=14):
        self.l, self.t, self.r, self.b = left, top, right, bottom
        self.xmax, self.ymax = xmax, ymax
        self.tick, self.label = tick, label   # font sizes; slide variants use larger ones

    def x(self, v):
        return self.l + (self.r - self.l) * v / self.xmax

    def y(self, v):
        return self.b - (self.b - self.t) * v / self.ymax

    def draw(self, xticks, yticks, xlabel, ylabel, xfmt=str, yfmt=str):
        out = []
        for v in yticks:
            out.append('<line x1="%.1f" x2="%.1f" y1="%.1f" y2="%.1f" stroke="%s"/>'
                       % (self.l, self.r, self.y(v), self.y(v), GRID))
            out.append(text(self.l - 8, self.y(v) + self.tick * 0.3, yfmt(v), self.tick, anchor='end'))
        for v in xticks:
            out.append(text(self.x(v), self.b + self.tick * 1.5, xfmt(v), self.tick, anchor='middle'))
        out.append('<line x1="%.1f" x2="%.1f" y1="%.1f" y2="%.1f" stroke="%s"/>'
                   % (self.l, self.r, self.b, self.b, INK_2))
        out.append(text((self.l + self.r) / 2, self.b + self.tick * 1.5 + self.label * 1.5, xlabel,
                        self.label, anchor='middle'))
        out.append('<text transform="translate(%.1f %.1f) rotate(-90)" font-size="%d" '
                   'fill="%s" text-anchor="middle">%s</text>'
                   % (self.l - 8 - self.tick * 2.2 - self.label * 0.7, (self.t + self.b) / 2,
                      self.label, INK_2, escape(ylabel)))
        return out


def polyline(points, color, width=2, dash=None, halo=False):
    pts = ' '.join('%.1f,%.1f' % p for p in points)
    out = []
    if halo:  # 2px surface ring where marks overlap
        out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="%d" '
                   'stroke-linejoin="round"/>' % (pts, SURFACE, width + 4))
    out.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="%d" '
               'stroke-linejoin="round"%s/>'
               % (pts, color, width, ' stroke-dasharray="%s"' % dash if dash else ''))
    return out


def steps(xs, ys):
    """Step-after path: a value holds until the next sample."""
    pts = []
    for i, (x, y) in enumerate(zip(xs, ys)):
        if i:
            pts.append((x, pts[-1][1]))
        pts.append((x, y))
    return pts


def legend(x, y, entries, spacing=220):
    """One row of line-swatch entries above the plot."""
    out = []
    for i, (label, color, dash) in enumerate(entries):
        lx = x + spacing * i
        out.append('<line x1="%d" x2="%d" y1="%d" y2="%d" stroke="%s" stroke-width="2"%s/>'
                   % (lx, lx + 22, y, y, color, ' stroke-dasharray="%s"' % dash if dash else ''))
        out.append(text(lx + 30, y + 4, label, 13, INK))
    return out


# ---------------------------------------------------------------- figures

def scale_figure(occupancy):
    pts = scale_points(occupancy)
    ax = Axes(96, 104, 800, 400, 600, 140)
    body = ax.draw(range(0, 601, 100), range(0, 141, 20),
                   'Unique 4,096-token prompts completed', 'Retained KV in CPU tier (GiB)')
    cap = occupancy['completed']['cache_capacity_GiB']
    body.append('<line x1="%.1f" x2="%.1f" y1="%.1f" y2="%.1f" stroke="%s" '
                'stroke-dasharray="6 4"/>' % (ax.l, ax.r, ax.y(cap), ax.y(cap), INK_2))
    body.append(text(ax.l + 6, ax.y(cap) - 8, 'Configured capacity %d GiB' % cap))
    body += polyline([(ax.x(n), ax.y(g)) for n, g in pts], BLUE)
    for n, g in pts:
        body.append('<circle cx="%.1f" cy="%.1f" r="4" fill="%s" stroke="%s" stroke-width="2"/>'
                    % (ax.x(n), ax.y(g), BLUE, SURFACE))
    n, g = pts[-1]
    body.append(text(ax.x(n) + 12, ax.y(g) + 4, '%.3f GiB retained' % g, 13, INK))
    body.append(text(ax.x(n) + 12, ax.y(g) + 22, '{:,} chunks'.format(occupancy['occupancy'][-1]['chunks'])))
    step = pts[1][1] - pts[0][1]
    caption = [
        'Job %s, Nov 10, 2026: one A100 80 GiB, 192 GiB job RAM allocation; Qwen2.5-7B BF16, LMCache 0.4.4, '
        'native prefix cache off.' % occupancy['job'],
        'Under-lock sums of live cache objects. Single tenant, no quotas. %d allocator-full warnings near capacity.'
        % occupancy['cache_full_warning_count'],
        'Observed cgroup high-water %.1f GiB, including file cache and runtime memory; not a minimum required '
        'allocation. Source: gpu-scale-occupancy.json.' % occupancy['max_sampled_cgroup_highwater_GiB'],
    ]
    title = 'Retained KV grows %.1f GiB per 100 prompts until the 128 GiB tier is full' % step
    subtitle = 'Directly measured retained KV bytes after every 100 prompts (GiB = 2^30 bytes)'
    data = {'points': [{'prompts': n, 'retained_GiB': g} for n, g in pts]}
    return frame(title, subtitle, caption, body), data


def quota_figure(timeline, analysis):
    rows, events = quota_series(timeline)
    ax = Axes(96, 132, 760, 404, 14, 140)
    body = ax.draw(range(0, 15, 2), [0, 42, 84, 126], 'Seconds since quota enforcer started',
                   'Retained KV per tenant (MiB)')
    labels = ['A quota lowered to 0', 'A quota raised to 126 MiB']
    for event, label in zip(events, labels):
        ex = ax.x(event['seconds'])
        body.append('<line x1="%.1f" x2="%.1f" y1="%.1f" y2="%.1f" stroke="%s" '
                    'stroke-dasharray="2 3"/>' % (ex, ex, ax.t - 4, ax.b, INK_2))
        body.append(text(ex + 6, ax.t + 6, label, 12))
    xs = [ax.x(r['seconds']) for r in rows]
    body += polyline(steps(xs, [ax.y(r['a_limit_MiB']) for r in rows]), INK_2, dash='6 4')
    body += polyline(steps(xs, [ax.y(r['a_MiB']) for r in rows]), BLUE)
    body += polyline(steps(xs, [ax.y(r['peer_each_MiB']) for r in rows]), ORANGE)
    # Where A equals the peers the lines coincide. Dash A over the peer line
    # there, so both identities stay visible and A's drop and refill read as
    # one continuous trace.
    overlaps = overlap_spans(rows)
    for x0, x1, value in overlaps:
        y = ax.y(value)
        body.append('<line x1="%.1f" x2="%.1f" y1="%.1f" y2="%.1f" stroke="%s" stroke-width="2" '
                    'stroke-dasharray="5 5"/>' % (ax.x(x0), ax.x(x1), y, y, BLUE))
    end = rows[-1]
    body.append(text(ax.r + 10, ax.y(end['a_MiB']) + 4, 'A: %d MiB' % end['a_MiB'], 13, INK))
    body.append(text(ax.r + 10, ax.y(end['peer_each_MiB']) + 4,
                     'B, C, D: %d MiB each' % end['peer_each_MiB'], 13, INK))
    body += legend(96, 94, [('A retained', BLUE, None),
                            ('B, C, D retained (each)', ORANGE, None),
                            ('A quota (limit)', INK_2, '6 4')], spacing=190)
    if overlaps:  # two-tone swatch matching the dashed overlap segments
        lx = 96 + 190 * 3
        body.append('<line x1="%d" x2="%d" y1="94" y2="94" stroke="%s" stroke-width="2"/>' % (lx, lx + 22, ORANGE))
        body.append('<line x1="%d" x2="%d" y1="94" y2="94" stroke="%s" stroke-width="2" '
                    'stroke-dasharray="5 5"/>' % (lx, lx + 22, BLUE))
        body.append(text(lx + 30, 98, 'A equal to B, C, D', 13, INK))
    low = [r for r in rows if events[0]['seconds'] <= r['seconds'] < events[1]['seconds']]
    zeros = sum(r['a_MiB'] == 0 for r in low)
    caption = [
        'Job 959878, Nov 10, 2026: one A30 24 GiB, 40 GiB job RAM allocation, 2 GiB CPU tier; 4 tagged tenants, '
        '%d requests in batches of 4.' % analysis['requests'],
        'Custom bounded hook, passes 100 ms apart, each sampled after its evictions; not stock LMCache quotas, '
        'not adaptive.',
        'Zero in %d/%d post-enforcement samples while lowered; %d/%d settled low-quota A requests missed. '
        'Source: gpu-primary-quota-*.json.'
        % (zeros, len(low), analysis['low_quota_A_lookup_misses'], analysis['low_quota_A_requests']),
    ]
    title = "Lowering tenant A's quota evicted only A's KV; B, C, D kept 42 MiB each"
    subtitle = 'Retained KV bytes per tenant during live inference, with two manual quota changes (MiB = 2^20 bytes)'
    data = {'events': events, 'samples': rows}
    return frame(title, subtitle, caption, body), data


def tenant_figure(first, repeat):
    outcomes = tenant_outcomes(first, repeat)
    names = {'cache_salt': 'cache_salt only', 'lmcache_tag': 'LMCache tenant tag'}
    rounds = {0: 'first request per tenant', 1: 'repeat request per tenant'}
    left, right, top = 360, 780, 190
    unit = (right - left) / 16.0
    body = [text(left, top - 34, 'Requests out of 16 tenants (identical 906-token prompt)', 13)]
    for i, (label, color) in enumerate([('Retrieved 768 tokens from CPU cache', BLUE),
                                        ('Missed (computed fresh)', ORANGE)]):
        lx = left + 300 * i
        body.append('<rect x="%d" y="%d" width="14" height="14" rx="3" fill="%s"/>'
                    % (lx, top - 76, color))
        body.append(text(lx + 22, top - 64, label, 13, INK))
    for i, o in enumerate(outcomes):
        y = top + i * 56 + (14 if o['mode'] == 'lmcache_tag' else 0)
        if o['repetition'] == 0:
            body.append(text(32, y + 17, names[o['mode']], 14, INK, weight='bold'))
        body.append(text(left - 12, y + 17, rounds[o['repetition']], 13, anchor='end'))
        clip = 'bar%d' % i
        body.append('<clipPath id="%s"><rect x="%.1f" y="%d" width="%.1f" height="24" rx="4"/></clipPath>'
                    % (clip, left, y, unit * o['requests']))
        x = left
        for count, color in [(o['retrieved_768'], BLUE), (o['misses'], ORANGE)]:
            if not count:
                continue
            w = unit * count
            gap = 2 if x + w < left + unit * o['requests'] - 0.5 else 0  # 2px surface gap
            body.append('<rect x="%.1f" y="%d" width="%.1f" height="24" fill="%s" clip-path="url(#%s)"/>'
                        % (x, y, w - gap, color, clip))
            body.append(text(x + (w - gap) / 2, y + 17, str(count), 13, '#ffffff', 'middle', 'bold'))
            x += w
        if o['mode'] == 'cache_salt' and o['repetition'] == 0 and o['retrieved_768']:
            body.append(text(right + 12, y + 17, '%d cross-tenant hits' % o['retrieved_768'], 13, INK))
    caption = [
        'Job 959878, Nov 10, 2026: one A30 24 GiB, 2 GiB CPU tier, LMCacheConnectorV1 (LMCache 0.4.4); 16 identities, sequential (concurrency 1).',
        'Identical counts in two fresh-process runs (gpu-tenants-first/repeat-summary.json). Connector-specific; not a security guarantee.',
    ]
    title = 'Tenant tags isolate identical prompts; cache_salt alone does not on this connector'
    subtitle = 'Isolation means each tenant’s first request misses; reuse means its repeat retrieves from the CPU cache'
    return frame(title, subtitle, caption, body), {'outcomes': outcomes}


# ---------------------------------------------------------------- slide variants
#
# For a slide the title, takeaway and caveats live on the slide itself, so these
# drop the embedded title and caption and use a compact canvas with large type:
# placed 6.2 in wide, 18 px renders at about 11 pt.

SW, SH = 720, 380


def slide_frame(alt, body):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
            'font-family="%s" role="img" aria-label="%s"><rect width="100%%" height="100%%" fill="%s"/>'
            '%s</svg>\n' % (SW, SH, SW, SH, FONT, escape(alt, {'"': '&quot;'}), SURFACE, ''.join(body)))


def swatch(x, y, label, color, dash=None, under=None, size=18):
    out = []
    if under:
        out.append('<line x1="%d" x2="%d" y1="%d" y2="%d" stroke="%s" stroke-width="3"/>'
                   % (x, x + 26, y, y, under))
    out.append('<line x1="%d" x2="%d" y1="%d" y2="%d" stroke="%s" stroke-width="3"%s/>'
               % (x, x + 26, y, y, color, ' stroke-dasharray="%s"' % dash if dash else ''))
    out.append(text(x + 34, y + 6, label, size, INK))
    return out


def slide_tenant(first, repeat):
    outcomes = tenant_outcomes(first, repeat)
    left, right = 250, 520
    unit = (right - left) / 16.0
    body = []
    for x, label, color in [(left, 'Retrieved from CPU cache', BLUE), (left + 285, 'Missed', ORANGE)]:
        body.append('<rect x="%d" y="14" width="18" height="18" rx="3" fill="%s"/>' % (x, color))
        body.append(text(x + 26, 30, label, 18, INK))
    names = {'cache_salt': 'cache_salt only', 'lmcache_tag': 'LMCache tenant tag'}
    rows = {0: 'First request', 1: 'Repeat request'}
    y = 64
    for o in outcomes:
        if o['repetition'] == 0:
            body.append(text(0, y + 22, names[o['mode']], 19, INK, weight='bold'))
            y += 34
        body.append(text(left - 12, y + 22, rows[o['repetition']], 18, anchor='end'))
        clip = 'sbar%s%d' % (o['mode'], o['repetition'])
        body.append('<clipPath id="%s"><rect x="%.1f" y="%d" width="%.1f" height="30" rx="4"/></clipPath>'
                    % (clip, left, y, unit * o['requests']))
        x = left
        for count, color in [(o['retrieved_768'], BLUE), (o['misses'], ORANGE)]:
            if not count:
                continue
            w = unit * count
            gap = 2 if x + w < left + unit * o['requests'] - 0.5 else 0
            body.append('<rect x="%.1f" y="%d" width="%.1f" height="30" fill="%s" clip-path="url(#%s)"/>'
                        % (x, y, w - gap, color, clip))
            body.append(text(x + (w - gap) / 2, y + 22, str(count), 18, '#ffffff', 'middle', 'bold'))
            x += w
        if o['mode'] == 'cache_salt' and o['repetition'] == 0 and o['retrieved_768']:
            body.append(text(right + 12, y + 22, '%d cross-tenant hits' % o['retrieved_768'], 18, INK))
        y += 44
        if o['mode'] == 'cache_salt' and o['repetition'] == 1:
            y += 14
    body.append(text(left, y + 20, 'Requests out of 16 tenants, identical 906-token prompt', 16))
    alt = 'Tenant isolation: cache_salt alone versus LMCache tenant tags, first and repeat requests'
    return slide_frame(alt, body)


def slide_quota(timeline):
    rows, events = quota_series(timeline)
    ax = Axes(78, 88, 560, 300, 14, 140, tick=18, label=18)
    body = ax.draw(range(0, 15, 2), [0, 42, 84, 126], 'Seconds since quota enforcer started',
                   'Retained KV (MiB)')
    for event, label in zip(events, ['A quota → 0', 'A quota → 126 MiB']):
        ex = ax.x(event['seconds'])
        body.append('<line x1="%.1f" x2="%.1f" y1="%.1f" y2="%.1f" stroke="%s" stroke-dasharray="2 3"/>'
                    % (ex, ex, ax.t - 18, ax.b, INK_2))
        body.append(text(ex + 6, ax.t - 6, label, 16))
    xs = [ax.x(r['seconds']) for r in rows]
    body += polyline(steps(xs, [ax.y(r['a_limit_MiB']) for r in rows]), INK_2, width=3, dash='7 5')
    body += polyline(steps(xs, [ax.y(r['a_MiB']) for r in rows]), BLUE, width=3)
    body += polyline(steps(xs, [ax.y(r['peer_each_MiB']) for r in rows]), ORANGE, width=3)
    for x0, x1, value in overlap_spans(rows):
        body.append('<line x1="%.1f" x2="%.1f" y1="%.1f" y2="%.1f" stroke="%s" stroke-width="3" '
                    'stroke-dasharray="6 6"/>' % (ax.x(x0), ax.x(x1), ax.y(value), ax.y(value), BLUE))
    end = rows[-1]
    body.append(text(ax.r + 10, ax.y(end['a_MiB']) + 6, 'A', 18, INK, weight='bold'))
    body.append(text(ax.r + 10, ax.y(end['peer_each_MiB']) + 6, 'B, C, D', 18, INK, weight='bold'))
    body += swatch(0, 22, 'A retained', BLUE)
    body += swatch(150, 22, 'B, C, D (each)', ORANGE)
    body += swatch(345, 22, 'A quota', INK_2, dash='7 5')
    body += swatch(490, 22, 'A = B, C, D', BLUE, dash='6 6', under=ORANGE)
    alt = "Per-tenant retained KV over time while tenant A's quota is lowered to zero and raised"
    return slide_frame(alt, body)


def slide_scale(occupancy):
    pts = scale_points(occupancy)
    ax = Axes(86, 24, 560, 296, 600, 140, tick=18, label=18)
    body = ax.draw(range(0, 601, 100), [0, 32, 64, 96, 128], 'Unique 4,096-token prompts completed',
                   'Retained KV (GiB)')
    cap = occupancy['completed']['cache_capacity_GiB']
    body.append('<line x1="%.1f" x2="%.1f" y1="%.1f" y2="%.1f" stroke="%s" stroke-dasharray="7 5"/>'
                % (ax.l, ax.r, ax.y(cap), ax.y(cap), INK_2))
    body.append(text(ax.l + 8, ax.y(cap) - 10, '%d GiB configured capacity' % cap, 16))
    body += polyline([(ax.x(n), ax.y(g)) for n, g in pts], BLUE, width=3)
    for n, g in pts:
        body.append('<circle cx="%.1f" cy="%.1f" r="5" fill="%s" stroke="%s" stroke-width="2"/>'
                    % (ax.x(n), ax.y(g), BLUE, SURFACE))
    n, g = pts[-1]
    body.append(text(ax.x(n) + 12, ax.y(g) + 6, '%.3f GiB' % g, 18, INK, weight='bold'))
    body.append(text(ax.x(n) + 12, ax.y(g) + 28, '{:,} chunks'.format(occupancy['occupancy'][-1]['chunks']), 16))
    alt = 'Retained KV in the CPU tier after every 100 prompts, up to the 128 GiB configured capacity'
    return slide_frame(alt, body)


# ---------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('evidence_dir', type=Path)
    parser.add_argument('out_dir', type=Path)
    args = parser.parse_args()
    evidence, out = args.evidence_dir.resolve(), args.out_dir.resolve()
    try:
        out.relative_to(evidence)
        parser.error('OUT_DIR must not be EVIDENCE_DIR or inside it; evidence is never written to')
    except ValueError:
        pass  # out is outside the evidence tree (case-insensitive aliases are not detected)

    def load(name):
        return json.loads((args.evidence_dir / name).read_text())

    figures = {
        'fig-scale-retained.svg': scale_figure(load('gpu-scale-occupancy.json')),
        'fig-quota-timeline.svg': quota_figure(load('gpu-primary-quota-timeline.json'),
                                               load('gpu-primary-quota-analysis.json')),
        'fig-tenant-isolation.svg': tenant_figure(load('gpu-tenants-first-summary.json'),
                                                  load('gpu-tenants-repeat-summary.json')),
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    data = {'note': 'Historical Nov 10, 2026 measurements replotted from saved files; no new run.'}
    for name, (svg, values) in figures.items():
        (args.out_dir / name).write_text(svg, encoding='utf-8')
        data[name] = values
    slides = {
        'slide-tenant-isolation.svg': slide_tenant(load('gpu-tenants-first-summary.json'),
                                                   load('gpu-tenants-repeat-summary.json')),
        'slide-quota-timeline.svg': slide_quota(load('gpu-primary-quota-timeline.json')),
        'slide-scale-retained.svg': slide_scale(load('gpu-scale-occupancy.json')),
    }
    for name, svg in slides.items():
        (args.out_dir / name).write_text(svg, encoding='utf-8')
    (args.out_dir / 'figure-data.json').write_text(json.dumps(data, indent=2))
    print('\n'.join(str(args.out_dir / n) for n in list(figures) + list(slides) + ['figure-data.json']))


if __name__ == '__main__':
    main()
