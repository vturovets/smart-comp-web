import { Button, List, ListItem, ListItemText, Stack, Typography } from "@mui/material";

import { Artifact } from "../api";

interface ArtifactsListProps {
  artifacts?: Artifact[];
  onDownload: (artifact: Artifact) => Promise<void>;
  showTitle?: boolean;
}

export function ArtifactsList({ artifacts = [], onDownload, showTitle = true }: ArtifactsListProps) {
  if (!artifacts.length) {
    return <Typography color="text.secondary">No artifacts yet. Downloads will appear after a job completes.</Typography>;
  }
  return (
    <Stack spacing={1}>
      {showTitle && <Typography variant="h6">Artifacts</Typography>}
      <List dense>
        {artifacts.map((artifact) => (
          <ListItem
            key={artifact.name}
            secondaryAction={
              <Button variant="outlined" onClick={() => onDownload(artifact)}>
                Download
              </Button>
            }
          >
            <ListItemText
              primary={artifact.name}
              secondary={`${artifact.contentType || "file"} • ${(artifact.sizeBytes / 1024).toFixed(1)} KB`}
            />
          </ListItem>
        ))}
      </List>
    </Stack>
  );
}
