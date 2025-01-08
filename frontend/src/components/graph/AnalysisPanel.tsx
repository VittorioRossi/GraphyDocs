import React, { useState } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { ChevronUp, ChevronDown, File, BarChart2 } from 'lucide-react';
import { Badge } from '@/components/ui/badge';

const NODE_COLORS: Record<string, string> = {
  'Project': '#4a5568', 'File': '#3182ce', 'Config': '#d69e2e',
  'Module': '#805ad5', 'Class': '#e53e3e', 'Method': '#38a169',
  'Function': '#2b6cb0', 'Variable': '#dd6b20', 'Constant': '#805ad5',
  'Namespace': '#718096', 'Interface': '#6b46c1', 'Enum': '#975a16',
  'Package': '#2c5282', 'Event': '#c53030', 'Operator': '#4c51bf',
  'default': '#a0aec0'
};

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  idle: { bg: 'bg-gray-100', text: 'text-gray-600' },
  running: { bg: 'bg-blue-100', text: 'text-blue-600' },
  completed: { bg: 'bg-green-100', text: 'text-green-600' },
  error: { bg: 'bg-red-100', text: 'text-red-600' },
  disconnected: { bg: 'bg-yellow-100', text: 'text-yellow-600' }
};

interface AnalysisStatus {
  status: string;
  progress: number;
  currentFile?: string;
  processedFiles: number;
  totalFiles: number;
  error?: string;
}

interface GraphStats {
  totalNodes: number;
  totalEdges: number;
  nodeTypes: Record<string, number>;
  edgeTypes: Record<string, number>;
}

interface AnalysisPanelProps {
  status: AnalysisStatus;
  stats: GraphStats;
}

const AnalysisPanel: React.FC<AnalysisPanelProps> = ({ status, stats }) => {
  const [isMinimized, setIsMinimized] = useState(false);

  const getStatusStyle = (statusStr: string) => {
    return STATUS_COLORS[statusStr] || STATUS_COLORS.idle;
  };

  return (
    <Card className="fixed right-4 top-4 transition-all duration-300 shadow-lg z-50 bg-white dark:bg-slate-900" 
         style={{ width: '24rem' }}>
      <CardHeader className="border-b pb-3 flex flex-row items-center justify-between cursor-pointer"
                 onClick={() => setIsMinimized(!isMinimized)}>
        <CardTitle className="text-lg font-semibold">Analysis Dashboard</CardTitle>
        <Button variant="ghost" size="icon">
          {isMinimized ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </Button>
      </CardHeader>
      
      <div className={`overflow-hidden transition-all duration-300 ${isMinimized ? 'max-h-0' : 'max-h-[600px]'}`}>
        <CardContent className="pt-4">
          <Tabs defaultValue="status">
            <TabsList className="w-full">
              <TabsTrigger value="status" className="w-1/2">
                <File className="h-4 w-4 mr-2" />
                Analysis Status
              </TabsTrigger>
              <TabsTrigger value="stats" className="w-1/2">
                <BarChart2 className="h-4 w-4 mr-2" />
                Graph Stats
              </TabsTrigger>
            </TabsList>

            <TabsContent value="status" className="space-y-4 mt-4">
              <Progress value={status.progress} className="mb-2" />
              <div className="space-y-2 text-sm">
                <div className="flex justify-between items-center">
                  <span className="font-medium">Status:</span>
                  <Badge variant="secondary" 
                         className={`${getStatusStyle(status.status).bg} ${getStatusStyle(status.status).text}`}>
                    {status.status}
                  </Badge>
                </div>
                {status.currentFile && (
                  <div className="flex justify-between">
                    <span className="font-medium">Current File:</span>
                    <span className="text-right truncate ml-2" title={status.currentFile}>
                      {status.currentFile.split('/').pop()}
                    </span>
                  </div>
                )}
                {status.error && (
                  <div className="text-red-500 mt-2">
                    Error: {status.error}
                  </div>
                )}
              </div>
            </TabsContent>

            <TabsContent value="stats" className="space-y-4 mt-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-slate-100 dark:bg-slate-800 p-3 rounded-lg">
                  <div className="text-2xl font-bold">{stats.totalNodes}</div>
                  <div className="text-sm text-muted-foreground">Total Nodes</div>
                </div>
                <div className="bg-slate-100 dark:bg-slate-800 p-3 rounded-lg">
                  <div className="text-2xl font-bold">{stats.totalEdges}</div>
                  <div className="text-sm text-muted-foreground">Total Edges</div>
                </div>
              </div>

              <div className="space-y-4">
                <div>
                  <h4 className="text-sm font-semibold mb-2">Node Types</h4>
                  <div className="space-y-1">
                    {Object.entries(stats.nodeTypes)
                      .sort(([, a], [, b]) => b - a)
                      .slice(0, 5)
                      .map(([type, count]) => (
                        <div key={type} className="flex justify-between text-sm items-center">
                          <div className="flex items-center gap-2">
                            <div className="w-3 h-3 rounded-full" 
                                 style={{ backgroundColor: NODE_COLORS[type] || NODE_COLORS.default }} />
                            <span>{type}</span>
                          </div>
                          <span className="font-medium">{count}</span>
                        </div>
                      ))}
                  </div>
                </div>

                <div>
                  <h4 className="text-sm font-semibold mb-2">Edge Types</h4>
                  <div className="space-y-1">
                    {Object.entries(stats.edgeTypes)
                      .sort(([, a], [, b]) => b - a)
                      .slice(0, 5)
                      .map(([type, count]) => (
                        <div key={type} className="flex justify-between text-sm">
                          <span>{type}</span>
                          <span className="font-medium">{count}</span>
                        </div>
                      ))}
                  </div>
                </div>
              </div>
            </TabsContent>
          </Tabs>
        </CardContent>
      </div>
    </Card>
  );
};

export type { AnalysisStatus, GraphStats };
export { AnalysisPanel as default };