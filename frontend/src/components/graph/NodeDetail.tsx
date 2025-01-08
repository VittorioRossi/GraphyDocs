import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { X } from 'lucide-react';

interface NodeDetailsCardProps {
    node: {
      name: string;
      type: string;
      data: {
        uri?: string;
        [key: string]: any;
      };
    };
    onClose: () => void;
  }

const NodeDetailsCard = ({ node, onClose }: NodeDetailsCardProps) => {
    const { name, type, data } = node;
    const uri = data?.uri || data?.path || 'N/A';

    return (
        <Card className="absolute top-4 left-4 w-96 z-10 shadow-lg">
        <CardHeader className="border-b flex flex-row items-center justify-between">
            <CardTitle className="text-lg font-semibold">{name}</CardTitle>
            <Button 
            variant="ghost" 
            size="icon" 
            onClick={onClose}
            className="h-8 w-8 rounded-full"
            >
            <X className="h-4 w-4" />
            </Button>
        </CardHeader>
        <CardContent className="space-y-4 pt-4">
            <div className="flex items-start space-x-2">
            <span className="font-bold min-w-16">Type:</span>
            <span className="text-sm">{type}</span>
            </div>
            <div className="flex items-start space-x-2">
            <span className="font-bold min-w-16">URI:</span>
            <span className="text-sm break-all">{uri}</span>
            </div>
        </CardContent>
        </Card>
    );
};

export default NodeDetailsCard;
