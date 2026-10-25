import type { Hero } from '../ai/heroView';

/** The checked result, large, over the model. A dash and a reason when no current checked plan exists. */
export function HeroNumber({ hero, forecast }: { hero: Hero; forecast?: string | null }) {
  return <div className={`hero${hero.ready ? '' : ' is-pending'}`} role="status" aria-label={hero.spoken}>
    <div className="hero-line" aria-hidden="true">
      <span key={hero.digits} className="hero-digits">{hero.digits}</span>
      <span className="hero-label">{hero.label}</span>
      {hero.delta && <span className={`chip hero-delta hero-delta-${hero.delta.tone}`} title={`Versus the previous result, ${hero.delta.versus}`}>{hero.delta.text}</span>}
    </div>
    {forecast && <p className="hero-forecast">{forecast}</p>}
    {hero.reason && <p className="hero-reason" aria-hidden="true">{hero.reason}</p>}
  </div>;
}
