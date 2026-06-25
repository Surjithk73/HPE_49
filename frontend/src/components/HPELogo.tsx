import React from 'react';

export const HPELogo = ({ width = 63, height = 18, style, className }: { width?: number | string, height?: number | string, style?: React.CSSProperties, className?: string }) => (
  <svg 
    version="1.0" 
    xmlns="http://www.w3.org/2000/svg" 
    viewBox="0 0 630 180" 
    style={{ ...style }} 
    width={width}
    height={height}
    className={className}
    xmlSpace="preserve"
  >
    <style>
      {`.st0{fill:none;stroke:var(--theme-tx-primary);stroke-width:36;}
        .st1{fill:none;stroke:#03A883;stroke-width:36;}`}
    </style>
    <path className="st0" d="M18,180V0 M172,180V0 M18,89h137 M250,180V0 M250,18h102c27.6,0,50,22.4,50,50s-22.4,50-50,50H250 M472,51V18 h158"/>
    <path className="st1" d="M630,162H472V86h158"/>
  </svg>
);
