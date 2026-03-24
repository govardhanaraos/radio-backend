import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../api/client";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { useToast } from "@/hooks/use-toast";

interface InListPlacement {
  enabled?: boolean;
  every_n_items?: number;
  first_ad_position?: number;
  max_ads?: number;
}

interface AdsConfig {
  id: string;
  screen?: string;
  ads_enabled?: boolean;
  banner_enabled?: boolean;
  interstitial_enabled?: boolean;
  interstitial_every_n_taps?: number;
  inlist_enabled?: boolean;
  stations_list?: InListPlacement;
  mp3_list?: InListPlacement;
  downloads_list?: InListPlacement;
  recordings_list?: InListPlacement;
}

function ListPlacementBlock({
  title,
  placement,
  onPatch,
}: {
  title: string;
  placement?: InListPlacement;
  onPatch: (p: Partial<InListPlacement>) => void;
}) {
  const p = placement ?? {};
  return (
    <div className="rounded-md border p-3 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">{title}</span>
        <Switch
          checked={p.enabled ?? false}
          onCheckedChange={(v) => onPatch({ enabled: v })}
        />
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <Label className="text-xs">Every N items</Label>
          <Input
            type="number"
            className="h-8"
            defaultValue={p.every_n_items ?? 3}
            onBlur={(e) =>
              onPatch({ every_n_items: parseInt(e.target.value, 10) || 1 })
            }
          />
        </div>
        <div>
          <Label className="text-xs">First ad position</Label>
          <Input
            type="number"
            className="h-8"
            defaultValue={p.first_ad_position ?? 0}
            onBlur={(e) =>
              onPatch({ first_ad_position: parseInt(e.target.value, 10) || 0 })
            }
          />
        </div>
        <div className="col-span-2">
          <Label className="text-xs">Max ads</Label>
          <Input
            type="number"
            className="h-8"
            defaultValue={p.max_ads ?? 0}
            onBlur={(e) => onPatch({ max_ads: parseInt(e.target.value, 10) || 0 })}
          />
        </div>
      </div>
    </div>
  );
}

export default function AdsConfigScreen() {
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const { data: configs, isLoading } = useQuery({
    queryKey: ["ads-config"],
    queryFn: async () => {
      const res = await apiClient.get<AdsConfig[]>("/ads-config/");
      return res.data;
    },
  });

  const mutation = useMutation({
    mutationFn: async ({ id, updates }: { id: string; updates: Partial<AdsConfig> }) => {
      const res = await apiClient.put(`/ads-config/${id}`, updates);
      return res.data;
    },
    onSuccess: () => {
      toast({ title: "Updated", description: "Ad settings updated." });
      queryClient.invalidateQueries({ queryKey: ["ads-config"] });
    },
    onError: (err) => {
      toast({ title: "Error", description: err.message, variant: "destructive" });
    },
  });

  const normalizeMutation = useMutation({
    mutationFn: async () => {
      const res = await apiClient.post<{ normalized: number }>("/ads-config/normalize-all");
      return res.data;
    },
    onSuccess: (data) => {
      toast({ title: "Normalized", description: `Updated ${data.normalized} document(s).` });
      queryClient.invalidateQueries({ queryKey: ["ads-config"] });
    },
    onError: (err) => {
      toast({ title: "Error", description: String(err), variant: "destructive" });
    },
  });

  const handleToggle = (id: string, field: keyof AdsConfig, val: boolean) => {
    mutation.mutate({ id, updates: { [field]: val } });
  };

  const patchList = (
    config: AdsConfig,
    listKey: "stations_list" | "mp3_list" | "downloads_list" | "recordings_list",
    partial: Partial<InListPlacement>
  ) => {
    const cur = config[listKey] ?? {};
    mutation.mutate({
      id: config.id,
      updates: { [listKey]: { ...cur, ...partial } } as Partial<AdsConfig>,
    });
  };

  if (isLoading) return <div className="p-8">Loading Ads Configurations...</div>;

  return (
    <div className="flex flex-col gap-6 w-full max-w-7xl mx-auto">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Ads Configuration</h2>
          <p className="text-muted-foreground">Manage ad toggles globally and per screen.</p>
          <p className="text-xs text-muted-foreground">
            Collection: <span className="font-mono">ads_config</span> | Key: <span className="font-mono">_id (id)</span>
          </p>
          <p className="text-xs text-muted-foreground mt-1 max-w-xl">
            Layout: <span className="font-mono">radio</span> → stations_list only;{" "}
            <span className="font-mono">player</span> → mp3_list, downloads_list, recordings_list;{" "}
            <span className="font-mono">mp3_download</span> → no in-list blocks stored (API returns disabled lists).
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={normalizeMutation.isPending}
          onClick={() => {
            if (confirm("Rewrite all ads_config documents to strip invalid list keys for each screen?")) {
              normalizeMutation.mutate();
            }
          }}
        >
          Normalize all in DB
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        {configs?.map((config) => {
          const screen = (config.screen || "").toLowerCase();
          const isGlobal = !config.screen;
          const isRadio = screen === "radio";
          const isPlayer = screen === "player";
          const isMp3Download = screen === "mp3_download";

          return (
            <Card key={config.id} className="flex flex-col">
              <CardHeader>
                <CardTitle className="capitalize">{config.screen || "Global Default"}</CardTitle>
                <CardDescription>ID: {config.id}</CardDescription>
                <p className="text-xs text-muted-foreground">
                  Collection: <span className="font-mono">ads_config</span> | Key:{" "}
                  <span className="font-mono">_id (id)</span>
                </p>
              </CardHeader>
              <CardContent className="flex-1 space-y-6">
                <div className="flex items-center justify-between">
                  <Label>Ads Enabled</Label>
                  <Switch
                    checked={config.ads_enabled || false}
                    onCheckedChange={(v) => handleToggle(config.id, "ads_enabled", v)}
                  />
                </div>

                {!isGlobal && (
                  <>
                    <div className="flex items-center justify-between">
                      <Label>Banner Enabled</Label>
                      <Switch
                        checked={config.banner_enabled || false}
                        onCheckedChange={(v) => handleToggle(config.id, "banner_enabled", v)}
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <Label>Interstitial Enabled</Label>
                      <Switch
                        checked={config.interstitial_enabled || false}
                        onCheckedChange={(v) => handleToggle(config.id, "interstitial_enabled", v)}
                      />
                    </div>
                    <div className="flex items-center justify-between gap-4">
                      <Label>Taps per Interstitial</Label>
                      <Input
                        type="number"
                        className="w-20"
                        key={`${config.id}-in-${config.interstitial_every_n_taps ?? 5}`}
                        defaultValue={config.interstitial_every_n_taps ?? 5}
                        onBlur={(e) =>
                          mutation.mutate({
                            id: config.id,
                            updates: {
                              interstitial_every_n_taps: Math.max(
                                1,
                                parseInt(e.target.value, 10) || 5
                              ),
                            },
                          })
                        }
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <Label>In-list Enabled</Label>
                      <Switch
                        checked={config.inlist_enabled || false}
                        onCheckedChange={(v) => handleToggle(config.id, "inlist_enabled", v)}
                      />
                    </div>
                  </>
                )}

                {isMp3Download && (
                  <p className="text-sm text-muted-foreground">
                    No in-list placement fields are stored for this screen. Clients receive disabled list
                    placement for all lists.
                  </p>
                )}

                {isRadio && (
                  <ListPlacementBlock
                    key={`${config.id}-sl-${JSON.stringify(config.stations_list)}`}
                    title="Stations list"
                    placement={config.stations_list}
                    onPatch={(partial) => patchList(config, "stations_list", partial)}
                  />
                )}

                {isPlayer && (
                  <div className="space-y-3">
                    <ListPlacementBlock
                      key={`${config.id}-mp3-${JSON.stringify(config.mp3_list)}`}
                      title="MP3 list"
                      placement={config.mp3_list}
                      onPatch={(partial) => patchList(config, "mp3_list", partial)}
                    />
                    <ListPlacementBlock
                      key={`${config.id}-dl-${JSON.stringify(config.downloads_list)}`}
                      title="Downloads list"
                      placement={config.downloads_list}
                      onPatch={(partial) => patchList(config, "downloads_list", partial)}
                    />
                    <ListPlacementBlock
                      key={`${config.id}-rl-${JSON.stringify(config.recordings_list)}`}
                      title="Recordings list"
                      placement={config.recordings_list}
                      onPatch={(partial) => patchList(config, "recordings_list", partial)}
                    />
                  </div>
                )}

                {!isGlobal && !isRadio && !isPlayer && !isMp3Download && config.screen && (
                  <p className="text-sm text-muted-foreground">
                    Unknown screen name: list fields are not edited here. Use Normalize or fix the{" "}
                    <span className="font-mono">screen</span> value.
                  </p>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
