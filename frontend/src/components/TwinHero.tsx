import type { TwinHero as Hero } from '../twin/twinHero';

/** The modeled figure over the scene, its model tag and the honest chips. Counts are crossings in the model, never survival. */
export function TwinHeroView({ hero, chips, title }: { hero: Hero; chips: string[]; title?: string }) {
  return <>
    <div className={`hero${hero.ready ? '' : ' is-pending'}`} role="status" aria-label={hero.spoken} title={title}>
      <div className="hero-line" aria-hidden="true">
        <span key={hero.digits} className="hero-digits">{hero.digits}</span>
        <span className="hero-label">{hero.label}</span>
        {hero.delta && !hero.withheld && <span className={`chip hero-delta hero-delta-${hero.delta.tone}`}>{hero.delta.text}</span>}
      </div>
      {hero.reason && <p className="hero-reason" aria-hidden="true">{hero.reason}</p>}
    </div>
    <div className="stage-chip-row">
      <span className="chip chip-data">{hero.tag}</span>
      {chips.map(chip => <span key={chip} className="chip chip-info">{chip}</span>)}
    </div>
  </>;
}
