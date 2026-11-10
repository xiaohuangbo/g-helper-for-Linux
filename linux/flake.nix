{
  description = "G-Helper for Linux";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      each = f: nixpkgs.lib.genAttrs systems (system: f (import nixpkgs { inherit system; }));
    in {
      packages = each (pkgs: {
        default = pkgs.callPackage ./default.nix { };
        ghelper = pkgs.callPackage ./default.nix { };
      });
    };
}
