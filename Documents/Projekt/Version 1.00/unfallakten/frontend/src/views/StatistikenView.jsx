import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, LineChart, Line } from "recharts";
import React, { useState } from "react";
import T from "../config/theme.js";
import Ic from "../config/icons.jsx";
import { MONATS } from "../config/constants.js";
import { fmtEuro } from "../config/utils.js";
import { Card } from "../components/common.jsx";

function StatistikenView() {
  const pie = [
    { name:"Offen",         value:8,  color:T.blue  },
    { name:"Regulierung",   value:14, color:T.amber },
    { name:"Abgeschlossen", value:22, color:T.green },
    { name:"Klage",         value:3,  color:T.red   },
  ];
  return (
    <div style={{ flex:1, overflowY:"auto", background:T.offWhite }}>
      <div style={{ maxWidth:1440, margin:"0 auto", padding:"1.75rem" }}>
        <div style={{ marginBottom:"1.5rem" }}>
          <h1 style={{ fontFamily:"'Bricolage Grotesque',sans-serif", fontSize:"2.0rem", fontWeight:700, color:T.navy, margin:0 }}>Statistiken</h1>
          <p style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.955rem", color:T.textMuted, marginTop:4 }}>
            Übersicht · Entwicklung · Status
          </p>
        </div>
        <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 220px", gap:"1rem", marginBottom:"1.5rem" }}>
          <Card><div style={{ padding:"1rem 1.4rem 0.4rem" }}>
            <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.825rem", fontWeight:600, color:T.textMuted, textTransform:"uppercase", letterSpacing:"0.08em", marginBottom:"0.8rem" }}>Neue Akten · 6 Monate</div>
            <ResponsiveContainer width="100%" height={180}><BarChart data={MONATS} barSize={20}><XAxis dataKey="m" tick={{fontSize:11,fontFamily:"'Figtree',sans-serif",fill:T.textMuted}} axisLine={false} tickLine={false}/><YAxis hide/><Tooltip contentStyle={{fontFamily:"'Figtree',sans-serif",fontSize:12,borderRadius:8,border:`1px solid ${T.border}`}} cursor={{fill:`${T.navy}08`}}/><Bar dataKey="a" fill={T.navy} radius={[4,4,0,0]}/></BarChart></ResponsiveContainer>
          </div></Card>
          <Card><div style={{ padding:"1rem 1.4rem 0.4rem" }}>
            <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.825rem", fontWeight:600, color:T.textMuted, textTransform:"uppercase", letterSpacing:"0.08em", marginBottom:"0.8rem" }}>Regulierungen (€) · 6 Monate</div>
            <ResponsiveContainer width="100%" height={180}><LineChart data={MONATS}><XAxis dataKey="m" tick={{fontSize:11,fontFamily:"'Figtree',sans-serif",fill:T.textMuted}} axisLine={false} tickLine={false}/><YAxis hide/><Tooltip formatter={v=>fmtEuro(v)} contentStyle={{fontFamily:"'Figtree',sans-serif",fontSize:12,borderRadius:8,border:`1px solid ${T.border}`}} cursor={{stroke:`${T.gold}44`}}/><Line type="monotone" dataKey="r" stroke={T.gold} strokeWidth={2.5} dot={{fill:T.gold,r:3}} activeDot={{r:5}}/></LineChart></ResponsiveContainer>
          </div></Card>
          <Card style={{ padding:"1rem 1.25rem" }}>
            <div style={{ fontFamily:"'Figtree',sans-serif", fontSize:"0.825rem", fontWeight:600, color:T.textMuted, textTransform:"uppercase", letterSpacing:"0.08em", marginBottom:"0.8rem" }}>Status-Verteilung</div>
            <ResponsiveContainer width="100%" height={130}><PieChart><Pie data={pie} cx="50%" cy="50%" innerRadius={35} outerRadius={55} dataKey="value" paddingAngle={2}>{pie.map((d,i) => <Cell key={i} fill={d.color}/>)}</Pie></PieChart></ResponsiveContainer>
            <div style={{ display:"flex", flexDirection:"column", gap:5, marginTop:8 }}>
              {pie.map((d,i) => <div key={i} style={{ display:"flex", alignItems:"center", justifyContent:"space-between", fontFamily:"'Figtree',sans-serif", fontSize:"0.825rem", color:T.textMid }}><span style={{ display:"flex", alignItems:"center", gap:6 }}><span style={{ width:8, height:8, borderRadius:2, background:d.color, flexShrink:0 }}/>{d.name}</span><strong>{d.value}</strong></div>)}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}


export default StatistikenView;
