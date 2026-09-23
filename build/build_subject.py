# -*- coding: utf-8 -*-
"""从壳模板 + 科目 DATA JSON 组装成科目 HTML，并做结构校验。

壳模板与数据源都在仓库 build/ 目录里（这是项目源头，随 git 走）。
用法：
  python build/build_subject.py <subject> <data_file> <out_file> <颜色串> <title> <h1> <sub> <about文案>
颜色串格式："#主色,#中色,#浅色,R,G,B"（RGB 逗号分隔）
"""
import io, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))  # build/ 目录
OUT_DIR = os.path.dirname(HERE)  # 仓库根

TYPES = ('choice', 'tf', 'fill', 'order', 'essay')

def read(p):
    return io.open(p, encoding='utf-8').read()

def norm(s):
    # 填空题答案比对用：去空格、去全角/半角标点差异
    return re.sub(r'[\s，。、；：！？·,.;:!?]', '', str(s)).lower()

def validate_quiz(c, quiz):
    for i, q in enumerate(quiz):
        loc = c['name'] + ' quiz#' + str(i)
        t = q.get('type', 'choice')  # 老数据无 type 视为 choice
        assert t in TYPES, loc + ' 未知题型 ' + t
        if t == 'choice':
            assert 0 <= q['ans'] < len(q['opts']), loc + ' 答案索引越界'
            assert len(q['opts']) == 4, loc + ' 选项不是4个'
        elif t == 'tf':
            assert isinstance(q['ans'], bool), loc + ' 判断题答案必须是 true/false'
        elif t == 'fill':
            assert q.get('a'), loc + ' 填空题缺答案 a'
            assert q['q'].count('____') >= 1, loc + ' 填空题缺下划线 ____'
        elif t == 'order':
            assert len(q.get('items', [])) >= 3, loc + ' 排序题至少3项'
        elif t == 'essay':
            assert q.get('mat'), loc + ' 材料题缺 mat'
            assert q.get('subs'), loc + ' 材料题缺 subs'
            for si, s in enumerate(q['subs']):
                assert isinstance(s.get('score'), int) and s['score'] > 0, loc + ' sub#' + str(si) + ' 分值非法'
                assert s.get('key'), loc + ' sub#' + str(si) + ' 缺参考要点 key'
        # 难度等级可选，默认2
        if 'lv' in q:
            assert q['lv'] in (1, 2, 3), loc + ' lv 必须是 1/2/3'

def build(subject, data_file, out_file, color_str, title, h1, sub, about_to):
    front = read(os.path.join(HERE, 'shell_front.txt'))
    back = read(os.path.join(HERE, 'shell_back.txt'))
    data = read(data_file)
    parsed = json.loads(data)  # 数据 JSON 必须合法，否则直接报错
    total_q = 0
    type_stat = {}
    for u in parsed['units']:
        assert u.get('chapters'), u['name'] + ' 没有章节'
        for c in u['chapters']:
            assert c.get('sections') and c.get('keypoints') and c.get('traps') and c.get('story') and c.get('quiz'), c['name'] + ' 缺字段'
            validate_quiz(c, c['quiz'])
            for q in c['quiz']:
                t = q.get('type', 'choice')
                type_stat[t] = type_stat.get(t, 0) + 1
            total_q += len(c['quiz'])
    parts = color_str.split(',')
    acc, mid, lite = parts[0], parts[1], parts[2]
    rgb = ','.join(parts[3:])
    # 主题色替换：只改 :root CSS 变量 + meta theme-color（定向，防误伤正文）
    assert '--acc:#2fa866;' in front, 'front 缺 --acc 锚点'
    assert '--mid:#57c785;' in front, 'front 缺 --mid 锚点'
    assert '--lite:#7fd9a4;' in front, 'front 缺 --lite 锚点'
    assert '--accrgb:47,168,102' in front, 'front 缺 --accrgb 锚点'
    assert '<meta name="theme-color" content="#34a86b">' in front, 'front 缺 theme-color 锚点'
    front = front.replace('--acc:#2fa866;', '--acc:' + acc + ';')
    front = front.replace('--mid:#57c785;', '--mid:' + mid + ';')
    front = front.replace('--lite:#7fd9a4;', '--lite:' + lite + ';')
    front = front.replace('--accrgb:47,168,102', '--accrgb:' + rgb)
    front = front.replace('<meta name="theme-color" content="#34a86b">',
                          '<meta name="theme-color" content="' + acc + '">')
    # back 里不允许出现主题色字面量（JS 应全部走 CSS 类）
    for hexc in ('#2fa866', '#57c785', '#7fd9a4', '#34a86b', '47,168,102'):
        assert hexc not in back, 'back 里发现主题色字面量 ' + hexc
    # localStorage 前缀按科目隔离（防止各科进度/错题互相覆盖）
    front = front.replace('biosw_', subject + '_')
    back = back.replace('biosw_', subject + '_')
    front = front.replace('<title>初一生物上册复习 · 苏科版 · 徐州</title>', '<title>' + title + '</title>')
    front = front.replace('<h1>🔬 初一生物上册复习</h1>', '<h1>' + h1 + '</h1>')
    front = front.replace(
        '<div class="sub">苏科版 · 2024秋 · 江苏徐州｜知识点 · 重点分析 · 易错点 · 习题 · 趣味故事</div>',
        '<div class="sub">' + sub + '</div>')
    about_from = '内容依据 <b>苏科版（江苏凤凰科学技术出版社）义务教育教科书·生物学七年级上册（2024秋版）</b> 整理，适用于江苏徐州初一学生。'
    assert about_from in back, 'about 锚文本没找到'
    back = back.replace(about_from, about_to)
    out = front + '<script type="application/json" id="DATA">\n' + data + '\n</script>' + back
    io.open(out_file, 'w', encoding='utf-8').write(out)
    scripts = re.findall(r'<script>(.*?)</script>', out, re.S)
    io.open(os.path.join(OUT_DIR, 'js_check.js'), 'w', encoding='utf-8').write('\n'.join(scripts))
    nch = sum(len(u['chapters']) for u in parsed['units'])
    print('OK %s | units=%d chapters=%d quiz=%d %s | %dKB' % (
        out_file, len(parsed['units']), nch, total_q, type_stat, len(out.encode('utf-8')) // 1024))

if __name__ == '__main__':
    build(*sys.argv[1:9])
