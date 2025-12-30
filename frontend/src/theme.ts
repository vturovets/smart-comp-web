import { createTheme } from "@mui/material/styles";

export const theme = createTheme({
  components: {
    MuiContainer: {
      defaultProps: {
        disableGutters: true
      },
      styleOverrides: {
        root: ({ theme }) => ({
          paddingLeft: theme.spacing(1),
          paddingRight: theme.spacing(1),
          [theme.breakpoints.up("sm")]: {
            paddingLeft: theme.spacing(1.5),
            paddingRight: theme.spacing(1.5)
          }
        }),
        disableGutters: ({ theme }) => ({
          paddingLeft: theme.spacing(1),
          paddingRight: theme.spacing(1),
          [theme.breakpoints.up("sm")]: {
            paddingLeft: theme.spacing(1.5),
            paddingRight: theme.spacing(1.5)
          }
        })
      }
    }
  }
});
