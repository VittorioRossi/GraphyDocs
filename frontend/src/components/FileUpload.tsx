import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useNavigate } from 'react-router-dom';
import { Progress } from "@/components/ui/progress";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger } from "@/components/ui/alert-dialog";
import { FaGithub, FaFile, FaTrash, FaEye } from 'react-icons/fa';
import { cn } from "@/lib/utils";

interface Project {
  id: string;
  name: string;
  source_type: 'git' | 'zip';
  created_at: string;
  analyzed: boolean;
}

interface UploadState {
  status: 'idle' | 'uploading' | 'complete' | 'error';
  progress: number;
  message: string;
  error?: string;
}

interface GithubCredentials {
  url: string;
  token?: string;
}

export function FileUpload() {
  const [githubUrl, setGithubUrl] = useState('');
  const [githubToken, setGithubToken] = useState('');
  const [projects, setProjects] = useState<Project[]>([]);
  const [uploadState, setUploadState] = useState<UploadState>({
    status: 'idle',
    progress: 0,
    message: ''
  });
  const navigate = useNavigate();

  useEffect(() => {
    fetchProjects();
  }, []);

  const fetchProjects = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/project/list');
      if (response.ok) {
        const data = await response.json();
        setProjects(data.elements);
      }
    } catch (error) {
      console.error('Failed to fetch projects:', error);
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    
    setUploadState({
      status: 'uploading',
      progress: 0,
      message: 'Uploading file...'
    });
  
    const formData = new FormData();
    formData.append('zip_file', file);
  
    try {
      const response = await fetch('http://localhost:8000/api/project/zip', {
        method: 'POST',
        body: formData,
      });
  
      if (!response.ok) throw new Error('Upload failed');

      fetchProjects();

      setUploadState({
        status: 'complete',
        progress: 100,
        message: 'Upload complete'
      });

      // Allow another file upload
      event.target.value = '';
    } catch (error) {
      setUploadState({
        status: 'error',
        progress: 0,
        message: 'Upload failed',
        error: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  };

  const handleGithubSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!githubUrl) return;

    setUploadState({
      status: 'uploading',
      progress: 0,
      message: 'Cloning repository...'
    });

    const payload: GithubCredentials = {
      url: githubUrl,
      ...(githubToken && { token: githubToken })
    };

    try {
      const response = await fetch('http://localhost:8000/api/project/git', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Repository clone failed');
      }

      fetchProjects();
      setUploadState({
        status: 'complete',
        progress: 100,
        message: 'Clone complete'
      });
      setGithubUrl('');
      setGithubToken('');
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      console.error('Clone failed:', errorMessage);
      setUploadState({
        status: 'error',
        progress: 0,
        message: `Clone failed: ${errorMessage}`,
        error: errorMessage
      });
    }
  };

  const handleDeleteProject = async (projectId: string) => {
    try {
      const response = await fetch(`http://localhost:8000/api/v1/manage/projects/${projectId}`, {
        method: 'DELETE',
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Delete failed');
      }

      // Refresh projects list after successful deletion
      fetchProjects();
    } catch (error) {
      console.error('Failed to delete project:', error);
      setUploadState({
        status: 'error',
        progress: 0,
        message: 'Delete failed',
        error: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-gradient-to-b from-slate-50 to-slate-100 p-6">
      <div className="w-full max-w-[800px] space-y-6">
        <Card className="bg-white shadow-xl border-0">
          <CardHeader className="border-b bg-white/50 backdrop-blur-sm">
            <CardTitle className="text-2xl font-bold text-slate-800">Project Upload</CardTitle>
          </CardHeader>
          <CardContent className="pt-6">
            <Tabs defaultValue="github" className="w-full">
              <TabsList className="grid w-full grid-cols-2 mb-6">
                <TabsTrigger value="file" className="flex items-center gap-2">
                  <FaFile className="h-4 w-4" />
                  File Upload
                </TabsTrigger>
                <TabsTrigger value="github" className="flex items-center gap-2">
                  <FaGithub className="h-4 w-4" />
                  GitHub URL
                </TabsTrigger>
              </TabsList>
            
              <TabsContent value="file">
                <div className="space-y-4">
                  <div className="border-2 border-dashed border-slate-200 rounded-lg p-8 text-center hover:border-slate-300 transition-colors">
                    <Input 
                      type="file" 
                      onChange={handleFileUpload}
                      accept=".zip,.tar.gz"
                      className="hidden"
                      id="file-upload"
                      disabled={uploadState.status === 'uploading'}
                    />
                    <label 
                      htmlFor="file-upload" 
                      className="cursor-pointer text-slate-600 hover:text-slate-800"
                    >
                      <FaFile className="h-8 w-8 mx-auto mb-2" />
                      <p className="font-medium">Drop your project file here or click to browse</p>
                      <p className="text-sm text-slate-500 mt-1">Supports .zip and .tar.gz files</p>
                    </label>
                  </div>
                </div>
              </TabsContent>
            
              <TabsContent value="github">
                <form onSubmit={handleGithubSubmit} className="space-y-4">
                  <div className="space-y-4">
                    <div className="relative">
                      <FaGithub className="absolute left-3 top-3 h-5 w-5 text-slate-400" />
                      <Input
                        type="url"
                        placeholder="https://github.com/username/repo"
                        value={githubUrl}
                        onChange={(e) => setGithubUrl(e.target.value)}
                        className="pl-10 border-2"
                        required
                        disabled={uploadState.status === 'uploading'}
                      />
                    </div>
                    <div className="relative">
                      <Input
                        type="password"
                        placeholder="GitHub Personal Access Token (optional)"
                        value={githubToken}
                        onChange={(e) => setGithubToken(e.target.value)}
                        className="border-2"
                        disabled={uploadState.status === 'uploading'}
                      />
                      <p className="text-xs text-slate-500 mt-1">
                        For private repositories, provide a GitHub token with repo access
                      </p>
                    </div>
                  </div>
                  <Button 
                    type="submit" 
                    disabled={uploadState.status === 'uploading'}
                    className="w-full bg-indigo-600 hover:bg-indigo-700"
                  >
                    Clone Repository
                  </Button>
                </form>
              </TabsContent>
            </Tabs>

            {uploadState.status !== 'idle' && (
              <div className="mt-6 space-y-4">
                <Progress value={uploadState.progress} className="h-2" />
                <p className={cn(
                  "text-sm text-center",
                  uploadState.status === 'error' ? 'text-red-600' : 'text-slate-600'
                )}>
                  {uploadState.message}
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {projects.length > 0 && (
          <Card className="bg-white shadow-xl border-0">
            <CardHeader className="border-b bg-white/50 backdrop-blur-sm">
              <CardTitle className="text-xl font-bold text-slate-800">Your Projects</CardTitle>
            </CardHeader>
            <CardContent className="pt-4">
              <div className="grid gap-4">
                {projects.map((project) => (
                  <div 
                    key={project.id}
                    className="flex items-center justify-between p-4 bg-white rounded-lg border border-slate-200 hover:border-slate-300 transition-colors"
                  >
                    <div>
                      <p className="font-medium text-slate-900">{project.name}</p>
                      <p className="text-sm text-slate-500">
                        Added {new Date(project.created_at).toLocaleDateString()} via {project.source_type}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        onClick={() => navigate(`/graph/${project.id}`)}
                        className="flex items-center gap-2"
                      >
                        <FaEye className="h-4 w-4" />
                        View
                      </Button>
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button
                            variant="destructive"
                            className="flex items-center gap-2"
                          >
                            <FaTrash className="h-4 w-4" />
                            Delete
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogTitle>Are you sure?</AlertDialogTitle>
                            <AlertDialogDescription>
                              This will permanently delete the project "{project.name}" and all its associated data.
                              This action cannot be undone.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction
                              onClick={() => handleDeleteProject(project.id)}
                              className="bg-red-600 hover:bg-red-700"
                            >
                              Delete Project
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}