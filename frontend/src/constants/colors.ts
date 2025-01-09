export const NODE_COLORS: Record<string, string> = {
    'Project': '#4a5568', 'File': '#3182ce', 'Config': '#d69e2e',
    'Module': '#805ad5', 'Class': '#e53e3e', 'Method': '#38a169',
    'Function': '#2b6cb0', 'Variable': '#dd6b20', 'Constant': '#805ad5',
    'Namespace': '#718096', 'Interface': '#6b46c1', 'Enum': '#975a16',
    'Package': '#2c5282', 'Event': '#c53030', 'Operator': '#4c51bf',
    'default': '#a0aec0'
};
  
export const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
    idle: { bg: 'bg-gray-100', text: 'text-gray-600' },
    running: { bg: 'bg-blue-100', text: 'text-blue-600' },
    completed: { bg: 'bg-green-100', text: 'text-green-600' },
    error: { bg: 'bg-red-100', text: 'text-red-600' },
    disconnected: { bg: 'bg-yellow-100', text: 'text-yellow-600' }
};