import { GooeyDemo } from './components/gooey-demo'
import { ResumeUpload } from './components/resume-upload'

function App() {
  return (
    <main className="min-h-screen bg-black">
      <GooeyDemo>
        <ResumeUpload />
      </GooeyDemo>
    </main>
  )
}

export default App
