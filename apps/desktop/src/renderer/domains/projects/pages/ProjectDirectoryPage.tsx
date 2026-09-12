import type { ComponentProps } from 'react'
import { ProjectDirectory } from '../components/ProjectDirectory'
export function ProjectDirectoryPage(props: ComponentProps<typeof ProjectDirectory>) { return <main className="mx-auto w-full max-w-7xl p-6"><ProjectDirectory {...props} /></main> }
