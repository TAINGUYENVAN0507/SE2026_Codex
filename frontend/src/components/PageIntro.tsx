import type { ReactNode } from 'react'

type PageIntroProps = {
  eyebrow: string
  title: string
  description: string
  action?: ReactNode
}

export function PageIntro({
  eyebrow,
  title,
  description,
  action,
}: PageIntroProps) {
  return (
    <header className="page-intro">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="page-description">{description}</p>
      </div>
      {action ? <div className="page-action">{action}</div> : null}
    </header>
  )
}
