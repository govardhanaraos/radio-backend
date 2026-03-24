import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import UnifiedView from "./stations/UnifiedView";
import RadioStationsManager from "./stations/RadioStationsManager";
import RadioGardenManager from "./stations/RadioGardenManager";

export default function StationsScreen() {
  return (
    <div className="flex flex-col gap-6 w-full max-w-7xl mx-auto">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Stations Management</h2>
        <p className="text-muted-foreground">
          View unified directories or edit underlying databases.
        </p>
        <p className="text-xs text-muted-foreground">
          Collections: <span className="font-mono">radio_stations</span> + <span className="font-mono">radio_garden_channels</span> | Key: <span className="font-mono">_id</span>
        </p>
      </div>

      <Tabs defaultValue="unified" className="w-full">
        <TabsList className="mb-4">
          <TabsTrigger value="unified">Unified Client View</TabsTrigger>
          <TabsTrigger value="radio-stations">Edit Radio Stations</TabsTrigger>
          <TabsTrigger value="radio-garden">Edit Radio Garden</TabsTrigger>
        </TabsList>
        <TabsContent value="unified">
          <UnifiedView />
        </TabsContent>
        <TabsContent value="radio-stations">
          <RadioStationsManager />
        </TabsContent>
        <TabsContent value="radio-garden">
          <RadioGardenManager />
        </TabsContent>
      </Tabs>
    </div>
  );
}
