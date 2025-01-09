import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { X } from 'lucide-react';
import { Node } from '@/types/graph';

interface NodeDetailsCardProps {
    node: Node;
    onClose: () => void;
  }

const NodeDetailsCard = ({ node, onClose }: NodeDetailsCardProps) => {
    const { name, kind, uri} = node;

    return (
        <Card className="absolute bottom-4 right-4 w-96 z-10 shadow-lg bg-white">
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
            <span className="text-sm">{kind}</span>
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
