import os

animations = {
    'brush-stroke.svg': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 40">
  <defs>
    <filter id="brushBlur">
      <feGaussianBlur stdDeviation="0.5"/>
    </filter>
    <linearGradient id="brushGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#1f1d1a" stop-opacity="0"/>
      <stop offset="30%" stop-color="#3d3a35" stop-opacity="0.8"/>
      <stop offset="70%" stop-color="#3d3a35" stop-opacity="0.8"/>
      <stop offset="100%" stop-color="#1f1d1a" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <path d="M10,20 Q40,10 60,20 Q80,30 110,20" fill="none" stroke="url(#brushGrad)" stroke-width="4" stroke-linecap="round" filter="url(#brushBlur)">
    <animate attributeName="stroke-dasharray" values="0 200;50 150;100 100;150 50;200 0" dur="2s" repeatCount="indefinite"/>
  </path>
</svg>''',

    'seal-stamp.svg': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 60 60">
  <rect x="5" y="5" width="50" height="50" fill="#a93226" rx="2">
    <animate attributeName="transform" values="scale(0);scale(1.2);scale(1)" dur="0.5s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0;1" dur="0.3s" repeatCount="indefinite"/>
  </rect>
  <text x="30" y="35" font-family="serif" font-size="20" fill="#fdfaf2" text-anchor="middle">印</text>
</svg>''',

    'petal-fall.svg': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 120">
  <g>
    <ellipse cx="20" cy="20" rx="6" ry="4" fill="#c9554a" opacity="0.6">
      <animate attributeName="cy" values="0;120" dur="4s" repeatCount="indefinite"/>
      <animate attributeName="cx" values="20;30;25;35;30" dur="4s" repeatCount="indefinite"/>
      <animate attributeName="rotate" values="0;360" dur="3s" repeatCount="indefinite"/>
    </ellipse>
    <ellipse cx="50" cy="40" rx="5" ry="3" fill="#d4756a" opacity="0.5">
      <animate attributeName="cy" values="10;130" dur="5s" repeatCount="indefinite"/>
      <animate attributeName="cx" values="50;45;55;50;60" dur="5s" repeatCount="indefinite"/>
      <animate attributeName="rotate" values="180;540" dur="4s" repeatCount="indefinite"/>
    </ellipse>
    <ellipse cx="80" cy="10" rx="5" ry="3" fill="#c9554a" opacity="0.5">
      <animate attributeName="cy" values="-5;125" dur="4.5s" repeatCount="indefinite"/>
      <animate attributeName="cx" values="80;75;85;80;70" dur="4.5s" repeatCount="indefinite"/>
      <animate attributeName="rotate" values="90;450" dur="3.5s" repeatCount="indefinite"/>
    </ellipse>
  </g>
</svg>''',

    'scroll-unfold.svg': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 160 100">
  <rect x="10" y="10" width="140" height="80" fill="#f7f2e8" stroke="#b08d57" stroke-width="2"/>
  <rect x="10" y="10" width="140" height="40" fill="#f7f2e8">
    <animate attributeName="height" values="0;40" dur="1.5s" repeatCount="indefinite"/>
  </rect>
  <rect x="10" y="50" width="140" height="40" fill="#f7f2e8">
    <animate attributeName="height" values="0;40" dur="1.5s" begin="0.5s" repeatCount="indefinite"/>
  </rect>
  <circle cx="15" cy="10" r="8" fill="#8b6914"/>
  <circle cx="145" cy="10" r="8" fill="#8b6914"/>
  <circle cx="15" cy="90" r="8" fill="#8b6914"/>
  <circle cx="145" cy="90" r="8" fill="#8b6914"/>
</svg>''',

    'floating-cloud.svg': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 60">
  <defs>
    <filter id="cloudBlur">
      <feGaussianBlur stdDeviation="1"/>
    </filter>
  </defs>
  <g filter="url(#cloudBlur)">
    <ellipse cx="30" cy="35" rx="20" ry="12" fill="#3d3a35" opacity="0.1">
      <animate attributeName="cx" values="20;40;20" dur="8s" repeatCount="indefinite"/>
      <animate attributeName="cy" values="35;30;35" dur="6s" repeatCount="indefinite"/>
    </ellipse>
    <ellipse cx="50" cy="30" rx="25" ry="15" fill="#3d3a35" opacity="0.08">
      <animate attributeName="cx" values="40;60;40" dur="10s" repeatCount="indefinite"/>
      <animate attributeName="cy" values="30;25;30" dur="7s" repeatCount="indefinite"/>
    </ellipse>
    <ellipse cx="70" cy="35" rx="18" ry="10" fill="#3d3a35" opacity="0.1">
      <animate attributeName="cx" values="60;80;60" dur="9s" repeatCount="indefinite"/>
      <animate attributeName="cy" values="35;40;35" dur="5s" repeatCount="indefinite"/>
    </ellipse>
  </g>
</svg>''',

    'ripple.svg': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 80">
  <circle cx="40" cy="40" r="5" fill="#5a7a6e" opacity="0.6">
    <animate attributeName="r" values="5;35" dur="2s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.6;0" dur="2s" repeatCount="indefinite"/>
  </circle>
  <circle cx="40" cy="40" r="5" fill="#5a7a6e" opacity="0.4">
    <animate attributeName="r" values="5;30" dur="2s" begin="0.5s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.4;0" dur="2s" begin="0.5s" repeatCount="indefinite"/>
  </circle>
  <circle cx="40" cy="40" r="5" fill="#5a7a6e" opacity="0.3">
    <animate attributeName="r" values="5;25" dur="2s" begin="1s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.3;0" dur="2s" begin="1s" repeatCount="indefinite"/>
  </circle>
</svg>''',

    'firefly.svg': '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 80">
  <circle cx="20" cy="30" r="2" fill="#f0e68c">
    <animate attributeName="cx" values="20;30;25;35;40;35;20" dur="5s" repeatCount="indefinite"/>
    <animate attributeName="cy" values="30;25;35;30;20;25;30" dur="4s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.3;1;0.5;1;0.3" dur="2s" repeatCount="indefinite"/>
    <animate attributeName="r" values="1.5;2.5;1.5" dur="1.5s" repeatCount="indefinite"/>
  </circle>
  <circle cx="60" cy="50" r="1.5" fill="#f0e68c">
    <animate attributeName="cx" values="60;70;65;55;50;60;60" dur="6s" repeatCount="indefinite"/>
    <animate attributeName="cy" values="50;45;55;50;60;55;50" dur="5s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.5;1;0.4;1;0.5" dur="2.5s" repeatCount="indefinite"/>
  </circle>
  <circle cx="80" cy="25" r="2" fill="#f0e68c">
    <animate attributeName="cx" values="80;90;85;75;80" dur="4s" repeatCount="indefinite"/>
    <animate attributeName="cy" values="25;20;30;25;35" dur="3.5s" repeatCount="indefinite"/>
    <animate attributeName="opacity" values="0.4;1;0.6;1;0.4" dur="2s" repeatCount="indefinite"/>
  </circle>
</svg>'''
}

base_dir = 'e:/javatexts/poetry-spring2/frontend/public/'
for filename, content in animations.items():
    filepath = os.path.join(base_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Created: {filename}')

print('\nAll animations created!')
