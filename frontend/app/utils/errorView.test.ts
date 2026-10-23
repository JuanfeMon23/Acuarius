import { describe, expect, it } from 'vitest'
import { errorView } from './errorView'

describe('errorView', () => {
  it.each([[404, 'No encontramos'], [403, 'No tienes permiso'], [503, 'No pudimos conectar'], [500, 'Algo salió mal'], [undefined, 'Algo salió mal']])(
    '%s', (status, start) => expect(errorView(status).title.startsWith(start)).toBe(true)
  )
})
