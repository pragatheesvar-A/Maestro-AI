"use client";

/**
 * Full-bleed animated background: a live-looking task-routing network,
 * rebuilt on pure CSS keyframe animations (transform / opacity /
 * stroke-dashoffset) instead of SVG SMIL (<animate>/<animateMotion>),
 * which some browsers and GPU-sandboxed/managed environments silently
 * refuse to run -- CSS animations are hardware-accelerated and always
 * play. Task nodes (squares) route through a pulsing central "optimizer"
 * hub out to employee nodes (circles); the connecting edges have a
 * flowing dash pattern to evoke continuous live routing, and soft
 * drifting glow orbs behind everything give it a premium "aurora" depth
 * that a static screenshot can't fully show but is unmistakable live.
 */
export default function AutomationBackground({ className = "" }: { className?: string }) {
  const tasks = [
    { id: "t1", x: 6, y: 14 }, { id: "t2", x: 4, y: 32 }, { id: "t3", x: 7, y: 50 },
    { id: "t4", x: 4, y: 68 }, { id: "t5", x: 7, y: 86 },
  ];
  const hub = { x: 34, y: 50 };
  const employees = [
    { id: "e1", x: 62, y: 10 }, { id: "e2", x: 66, y: 26 }, { id: "e3", x: 60, y: 44 },
    { id: "e4", x: 67, y: 60 }, { id: "e5", x: 61, y: 76 }, { id: "e6", x: 66, y: 92 },
  ];
  const farNodes = [
    { x: 88, y: 8 }, { x: 94, y: 22 }, { x: 90, y: 38 }, { x: 96, y: 54 },
    { x: 88, y: 70 }, { x: 93, y: 86 }, { x: 84, y: 96 },
  ];
  const hotEdges = new Set(["t1-e2", "t3-e4", "t5-e6"]);

  return (
    <div className={`relative ${className}`}>
      {/* Drifting glow orbs -- always-on ambient motion, independent of SVG support */}
      <div
        className="absolute rounded-full animate-drift-orb"
        style={{ width: "42%", height: "42%", left: "6%", top: "8%", background: "radial-gradient(circle, rgba(255,255,255,0.16), transparent 70%)", filter: "blur(30px)" }}
      />
      <div
        className="absolute rounded-full animate-drift-orb"
        style={{ width: "36%", height: "36%", right: "8%", bottom: "10%", background: "radial-gradient(circle, rgba(255,255,255,0.14), transparent 70%)", filter: "blur(30px)", animationDelay: "-6s" }}
      />
      <div
        className="absolute rounded-full animate-drift-orb"
        style={{ width: "30%", height: "30%", left: "40%", top: "35%", background: "radial-gradient(circle, rgba(255,255,255,0.10), transparent 70%)", filter: "blur(26px)", animationDelay: "-3s" }}
      />

      <svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice" className="absolute inset-0 w-full h-full" xmlns="http://www.w3.org/2000/svg">
        {/* task -> hub edges */}
        {tasks.map((t) => {
          const hot = hotEdges.has(`${t.id}-e2`);
          return (
            <line
              key={`th-${t.id}`} x1={t.x} y1={t.y} x2={hub.x} y2={hub.y}
              stroke={hot ? "rgba(255,255,255,0.65)" : "rgba(255,255,255,0.14)"}
              strokeWidth={hot ? 0.35 : 0.15}
              className={hot ? "animate-dash-flow" : ""}
            />
          );
        })}
        {/* hub -> employee edges */}
        {employees.map((e, i) => {
          const hot = hotEdges.has(`t1-${e.id}`) || hotEdges.has(`t3-${e.id}`) || hotEdges.has(`t5-${e.id}`);
          return (
            <line
              key={`he-${e.id}`} x1={hub.x} y1={hub.y} x2={e.x} y2={e.y}
              stroke={hot ? "rgba(255,255,255,0.65)" : "rgba(255,255,255,0.14)"}
              strokeWidth={hot ? 0.35 : 0.15}
              className={hot ? "animate-dash-flow" : ""}
              style={hot ? { animationDelay: `${i * 0.15}s` } : undefined}
            />
          );
        })}
        {/* employee -> far decorative nodes (ambience only) */}
        {employees.slice(0, farNodes.length).map((e, i) => (
          <line key={`ef-${i}`} x1={e.x} y1={e.y} x2={farNodes[i].x} y2={farNodes[i].y} stroke="rgba(255,255,255,0.06)" strokeWidth={0.12} />
        ))}

        {/* hub node: solid core + continuous expanding pulse ring */}
        <circle cx={hub.x} cy={hub.y} r={1.8} fill="rgba(255,255,255,0.2)" stroke="rgba(255,255,255,0.65)" strokeWidth={0.15} />
        <circle cx={hub.x} cy={hub.y} r={1.8} fill="none" stroke="white" strokeWidth={0.15} className="animate-ring-expand" />

        {/* task nodes */}
        {tasks.map((t, i) => (
          <rect
            key={t.id} x={t.x - 0.9} y={t.y - 0.9} width={1.8} height={1.8} rx={0.5}
            fill="rgba(255,255,255,0.18)" stroke="rgba(255,255,255,0.55)" strokeWidth={0.13}
            className="animate-node-pulse" style={{ animationDelay: `${i * 0.3}s` }}
          />
        ))}
        {/* employee nodes */}
        {employees.map((e, i) => (
          <circle
            key={e.id} cx={e.x} cy={e.y} r={1.1}
            fill="rgba(255,255,255,0.18)" stroke="rgba(255,255,255,0.55)" strokeWidth={0.13}
            className="animate-node-pulse" style={{ animationDelay: `${i * 0.25 + 0.6}s` }}
          />
        ))}
        {/* faint ambient far nodes */}
        {farNodes.map((n, i) => (
          <circle key={i} cx={n.x} cy={n.y} r={0.5} fill="rgba(255,255,255,0.3)" className="animate-twinkle" style={{ animationDelay: `${i * 0.4}s` }} />
        ))}
      </svg>
    </div>
  );
}
