import {
  createContext,
  useContext,
  useState,
  type PropsWithChildren,
} from 'react'
import { seedMeetings, type Meeting } from './model'

interface Store {
  meetings: Meeting[]
  files: Record<string, File>
  update: (id: string, transform: (m: Meeting) => Meeting) => void
  add: (meeting: Meeting, file: File) => void
  reset: () => void
}
const Context = createContext<Store | null>(null)

export function DemoStore({ children }: PropsWithChildren) {
  // Keeps the demo meeting and selected local audio in memory for preview.
  const [meetings, setMeetings] = useState(seedMeetings)
  const [files, setFiles] = useState<Record<string, File>>({})
  return (
    <Context.Provider
      value={{
        meetings,
        files,
        reset: () => {
          setMeetings(seedMeetings())
          setFiles({})
        },
        update: (id, transform) =>
          setMeetings((items) =>
            items.map((m) => (m.id === id ? transform(m) : m)),
          ),
        add: (meeting, file) => {
          setMeetings((items) => [meeting, ...items])
          setFiles((items) => ({ ...items, [meeting.id]: file }))
        },
      }}
    >
      {children}
    </Context.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useMeetings() {
  const store = useContext(Context)
  if (!store) throw new Error('Meeting store is missing')
  return store
}
