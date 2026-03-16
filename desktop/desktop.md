<

<?xml version="1.0" encoding="UTF-8"?>
<svg
    xmlns="http://www.w3.org/2000/svg"
    width="1920"
    height="1080"
    viewBox="0 0 1920 1080"
    style="background:#050814; font-family:'Segoe UI', sans-serif;">

  <!-- =========
       DEFS: Verläufe, Glows, Filter
       ========= -->
  <defs>
    <!-- Hintergrund-Gradient -->
    <linearGradient id="bgGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#050814"/>
      <stop offset="50%" stop-color="#071426"/>
      <stop offset="100%" stop-color="#02040a"/>
    </linearGradient>

    <!-- Glow für Kugel -->
    <radialGradient id="orbGrad" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#4ff6ff" stop-opacity="1"/>
      <stop offset="40%" stop-color="#2bd0ff" stop-opacity="0.9"/>
      <stop offset="70%" stop-color="#0a7fa8" stop-opacity="0.7"/>
      <stop offset="100%" stop-color="#00141f" stop-opacity="0"/>
    </radialGradient>

    <!-- Inneres Muster der Kugel -->
    <radialGradient id="orbCoreGrad" cx="50%" cy="40%" r="50%">
      <stop offset="0%" stop-color="#b8ffff" stop-opacity="1"/>
      <stop offset="40%" stop-color="#5cf0ff" stop-opacity="0.9"/>
      <stop offset="80%" stop-color="#007a99" stop-opacity="0.4"/>
      <stop offset="100%" stop-color="#003344" stop-opacity="0"/>
    </radialGradient>

    <!-- Warmes Metall für Maschine -->
    <linearGradient id="metalGrad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#3b2410"/>
      <stop offset="30%" stop-color="#7b4a1c"/>
      <stop offset="60%" stop-color="#c28a4a"/>
      <stop offset="100%" stop-color="#f0c27b"/>
    </linearGradient>

    <!-- Kupferrohr -->
    <linearGradient id="pipeGrad" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#f0c27b"/>
      <stop offset="50%" stop-color="#b87333"/>
      <stop offset="100%" stop-color="#5a2c0a"/>
    </linearGradient>

    <!-- Daten-Licht in Rohren -->
    <linearGradient id="dataFlowGrad" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#00f5ff" stop-opacity="0.1"/>
      <stop offset="40%" stop-color="#00f5ff" stop-opacity="0.8"/>
      <stop offset="100%" stop-color="#00f5ff" stop-opacity="0.1"/>
    </linearGradient>

    <!-- Glow-Filter -->
    <filter id="softGlow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="8" result="blur"/>
      <feColorMatrix
        in="blur"
        type="matrix"
        values="0 0 0 0 0
                0 0 0 0 0.9
                0 0 0 0 1
                0 0 0 0.8 0"
        result="glow"/>
      <feMerge>
        <feMergeNode in="glow"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>

    <!-- Glow für Netzwerk-Linien -->
    <filter id="lineGlow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="3" result="blur"/>
      <feColorMatrix
        in="blur"
        type="matrix"
        values="0 0 0 0 0
                0 0 0 0.8 1
                0 0 0 0.9 1
                0 0 0 0.9 0"
        result="glow"/>
      <feMerge>
        <feMergeNode in="glow"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>

    <!-- Glow für rote / gelbe Warnungen -->
    <filter id="alertGlow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="4" result="blur"/>
      <feColorMatrix
        in="blur"
        type="matrix"
        values="1 0 0 0 0
                0.4 0 0 0 0
                0 0 0 0 0
                0 0 0 0.9 0"
        result="glow"/>
      <feMerge>
        <feMergeNode in="glow"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>

  </defs>

  <!-- =========
       HINTERGRUND
       ========= -->
  <rect x="0" y="0" width="1920" height="1080" fill="url(#bgGrad)"/>

  <!-- Leichtes Netzwerk im Hintergrund -->
  <g id="backgroundNetwork" stroke="#0b2b3f" stroke-width="1" opacity="0.4">
    <!-- Ein paar abstrakte Linien / Knoten -->
    <polyline points="100 200 300 150 600 220 900 180 1200 260 1500 210 1800 260"
              fill="none"/>
    <polyline points="200 500 450 430 700 520 1000 480 1300 560 1600 520"
              fill="none"/>
    <polyline points="150 800 400 720 750 780 1100 740 1450 820 1750 780"
              fill="none"/>

    <!-- Knoten -->
    <circle cx="300" cy="150" r="4" fill="#0ff"/>
    <circle cx="700" cy="520" r="4" fill="#0ff"/>
    <circle cx="1450" cy="820" r="4" fill="#0ff"/>
    <circle cx="1200" cy="260" r="4" fill="#0ff"/>
  </g>

  <!-- =========
       ZENTRALE KUGEL
       ========= -->
  <g id="centralOrb" transform="translate(960,380)">
    <!-- Äußerer Glow -->
    <circle r="190" fill="url(#orbGrad)" filter="url(#softGlow)" opacity="0.9">
      <!-- Puls-Animation -->
      <animate attributeName="r"
               values="180;195;180"
               dur="6s"
               repeatCount="indefinite"/>
    </circle>

    <!-- Innerer Kern -->
    <circle r="120" fill="url(#orbCoreGrad)" opacity="0.95">
      <animate attributeName="r"
               values="110;130;110"
               dur="8s"
               repeatCount="indefinite"/>
    </circle>

    <!-- Fraktal-artige Linien (vereinfacht) -->
    <path d="M -80 -20 C -40 -80, 40 -80, 80 -20
             S 40 60, -20 80
             S -90 40, -80 -20 Z"
          fill="none"
          stroke="#b8ffff"
          stroke-width="2"
          opacity="0.6">
      <animateTransform attributeName="transform"
                        type="rotate"
                        from="0"
                        to="360"
                        dur="30s"
                        repeatCount="indefinite"/>
    </path>

    <!-- Satelliten-Kugeln -->
    <g id="satellites">
      <circle cx="0" cy="-230" r="18" fill="#4ff6ff" opacity="0.9"/>
      <circle cx="200" cy="0" r="14" fill="#4ff6ff" opacity="0.7"/>
      <circle cx="-190" cy="40" r="12" fill="#4ff6ff" opacity="0.7"/>

      <!-- leichte Orbit-Animation -->
      <animateTransform attributeName="transform"
                        type="rotate"
                        from="0"
                        to="360"
                        dur="40s"
                        repeatCount="indefinite"/>
    </g>
  </g>

  <!-- =========
       STEAMPUNK-MASCHINE UNTEN
       ========= -->
  <g id="machine" transform="translate(0,720)">
    <!-- Basisplatte -->
    <rect x="200" y="260" width="1520" height="80" rx="10" ry="10"
          fill="url(#metalGrad)" stroke="#2a1608" stroke-width="3"/>

    <!-- Hauptgehäuse -->
    <rect x="420" y="80" width="1080" height="200" rx="20" ry="20"
          fill="url(#metalGrad)" stroke="#2a1608" stroke-width="4"/>

    <!-- Linker Zylinder / Kolben -->
    <g id="leftPiston" transform="translate(480,120)">
      <rect x="-30" y="0" width="60" height="120" rx="10" ry="10"
            fill="#3b2410" stroke="#f0c27b" stroke-width="3"/>
      <rect x="-18" y="-40" width="36" height="60" rx="8" ry="8"
            fill="#7b4a1c" stroke="#f0c27b" stroke-width="2">
        <animate attributeName="y"
                 values="-40;-20;-40"
                 dur="1.2s"
                 repeatCount="indefinite"/>
      </rect>
    </g>

    <!-- Rechter Zylinder / Kolben -->
    <g id="rightPiston" transform="translate(1440,120)">
      <rect x="-30" y="0" width="60" height="120" rx="10" ry="10"
            fill="#3b2410" stroke="#f0c27b" stroke-width="3"/>
      <rect x="-18" y="-40" width="36" height="60" rx="8" ry="8"
            fill="#7b4a1c" stroke="#f0c27b" stroke-width="2">
        <animate attributeName="y"
                 values="-20;-40;-20"
                 dur="1.4s"
                 repeatCount="indefinite"/>
      </rect>
    </g>

    <!-- Zahnräder -->
    <g id="gears" transform="translate(960,180)">
      <!-- Einfaches Zahnrad (vereinfachte Darstellung) -->
      <circle r="60" fill="#3b2410" stroke="#f0c27b" stroke-width="4"/>
      <circle r="20" fill="#f0c27b"/>

      <!-- Zähne als kleine Rechtecke -->
      <g id="gearTeeth">
        <rect x="-6" y="-80" width="12" height="20" fill="#f0c27b"/>
        <rect x="-6" y="60" width="12" height="20" fill="#f0c27b"/>
        <rect x="-80" y="-6" width="20" height="12" fill="#f0c27b"/>
        <rect x="60" y="-6" width="20" height="12" fill="#f0c27b"/>
      </g>

      <animateTransform attributeName="transform"
                        type="rotate"
                        from="0"
                        to="360"
                        dur="10s"
                        repeatCount="indefinite"/>
    </g>

    <!-- Anzeigen: CPU / RAM -->
    <g id="gauges" transform="translate(720,110)">
      <!-- CPU-Anzeige -->
      <rect x="0" y="0" width="180" height="70" rx="10" ry="10"
            fill="#111" stroke="#f0c27b" stroke-width="3"/>
      <text x="20" y="28" fill="#f0c27b" font-size="20" font-weight="bold">CPU</text>
      <!-- Balken -->
      <rect x="20" y="40" width="140" height="16" rx="8" ry="8"
            fill="#222"/>
      <rect x="20" y="40" width="90" height="16" rx="8" ry="8"
            fill="#ff4b3a">
        <animate attributeName="width"
                 values="40;150;60;120;90"
                 dur="6s"
                 repeatCount="indefinite"/>
      </rect>

      <!-- RAM-Anzeige -->
      <g transform="translate(260,0)">
        <rect x="0" y="0" width="180" height="70" rx="10" ry="10"
              fill="#111" stroke="#f0c27b" stroke-width="3"/>
        <text x="20" y="28" fill="#f0c27b" font-size="20" font-weight="bold">RAM</text>
        <rect x="20" y="40" width="140" height="16" rx="8" ry="8"
              fill="#222"/>
        <rect x="20" y="40" width="70" height="16" rx="8" ry="8"
              fill="#9b59ff">
          <animate attributeName="width"
                   values="50;120;80;140;70"
                   dur="7s"
                   repeatCount="indefinite"/>
        </rect>
      </g>
    </g>
  </g>

  <!-- =========
       ROHRE & DATENFLUSS ZUR KUGEL
       ========= -->
  <g id="pipesAndData">
    <!-- Linkes Rohr -->
    <path d="M 600 720
             C 650 620, 750 540, 880 480
             C 910 465, 930 450, 960 430"
          fill="none"
          stroke="url(#pipeGrad)"
          stroke-width="18"
          stroke-linecap="round"/>

    <!-- Rechtes Rohr -->
    <path d="M 1320 720
             C 1270 620, 1170 540, 1040 480
             C 1010 465, 990 450, 960 430"
          fill="none"
          stroke="url(#pipeGrad)"
          stroke-width="18"
          stroke-linecap="round"/>

    <!-- Datenfluss (heller Kern im Rohr) -->
    <path d="M 600 720
             C 650 620, 750 540, 880 480
             C 910 465, 930 450, 960 430"
          fill="none"
          stroke="url(#dataFlowGrad)"
          stroke-width="6"
          stroke-linecap="round"
          filter="url(#lineGlow)">
      <animate attributeName="stroke-dasharray"
               values="0,400;200,400;0,400"
               dur="3s"
               repeatCount="indefinite"/>
      <animate attributeName="stroke-dashoffset"
               values="0;-400"
               dur="3s"
               repeatCount="indefinite"/>
    </path>

    <path d="M 1320 720
             C 1270 620, 1170 540, 1040 480
             C 1010 465, 990 450, 960 430"
          fill="none"
          stroke="url(#dataFlowGrad)"
          stroke-width="6"
          stroke-linecap="round"
          filter="url(#lineGlow)">
      <animate attributeName="stroke-dasharray"
               values="0,400;200,400;0,400"
               dur="3s"
               repeatCount="indefinite"/>
      <animate attributeName="stroke-dashoffset"
               values="0;-400"
               dur="3s"
               repeatCount="indefinite"/>
    </path>
  </g>

  <!-- =========
       NETZWERK-KNOTEN & VERBINDUNGEN
       ========= -->
  <g id="network" stroke-width="3" fill="none">

    <!-- Verbindungslinien von Kugel zu Knoten -->
    <g stroke="#00f5ff" filter="url(#lineGlow)">
      <!-- YouTube -->
      <line x1="960" y1="380" x2="420" y2="260"/>
      <!-- Google -->
      <line x1="960" y1="380" x2="1380" y2="260"/>
      <!-- NAS -->
      <line x1="960" y1="380" x2="1500" y2="520"/>
      <!-- Smartphone -->
      <line x1="960" y1="380" x2="380" y2="520"/>
    </g>

    <!-- YouTube-Knoten -->
    <g id="nodeYouTube" transform="translate(420,260)">
      <circle r="32" fill="#ff2b2b" filter="url(#alertGlow)"/>
      <rect x="-26" y="-18" width="52" height="36" rx="8" ry="8"
            fill="#b00000"/>
      <polygon points="-6,-10 10,0 -6,10" fill="#ffffff"/>
      <text x="0" y="52" text-anchor="middle"
            fill="#ffb3b3" font-size="18">YouTube</text>
    </g>

    <!-- Google-Knoten -->
    <g id="nodeGoogle" transform="translate(1380,260)">
      <polygon points="-30,-30 30,-30 30,30 -30,30"
               fill="#ffffff" opacity="0.9" filter="url(#softGlow)"/>
      <circle r="20" fill="none" stroke="#4285F4" stroke-width="4"/>
      <path d="M -10 -5 H 10"
            stroke="#34A853" stroke-width="4"/>
      <path d="M 0 -10 V 10"
            stroke="#EA4335" stroke-width="4"/>
      <text x="0" y="52" text-anchor="middle"
            fill="#e0f0ff" font-size="18">Google</text>
    </g>

    <!-- NAS-Knoten -->
    <g id="nodeNAS" transform="translate(1500,520)">
      <circle r="40" fill="#111" stroke="#555" stroke-width="4"/>
      <rect x="-22" y="-18" width="44" height="12" rx="3" ry="3"
            fill="#333"/>
      <rect x="-22" y="4" width="44" height="12" rx="3" ry="3"
            fill="#333"/>
      <circle cx="24" cy="-12" r="3" fill="#0f0"/>
      <circle cx="24" cy="10" r="3" fill="#0f0"/>
      <text x="0" y="60" text-anchor="middle"
            fill="#c0d0ff" font-size="18">NAS</text>
    </g>

    <!-- Smartphone-Knoten -->
    <g id="nodePhone" transform="translate(380,520)">
      <rect x="-20" y="-36" width="40" height="72" rx="8" ry="8"
            fill="#111" stroke="#00f5ff" stroke-width="3"/>
      <rect x="-14" y="-28" width="28" height="48" rx="4" ry="4"
            fill="#0b1a26"/>
      <circle cx="0" cy="30" r="3" fill="#00f5ff"/>
      <text x="0" y="60" text-anchor="middle"
            fill="#a8e8ff" font-size="18">Smartphone</text>
    </g>
  </g>

</svg>