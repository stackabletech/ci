{
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
    rust-overlay = {
      url = "github:oxalica/rust-overlay";
      inputs = {
        nixpkgs.follows = "nixpkgs";
        flake-utils.follows = "flake-utils";
      };
    };
  };
  outputs = { self, nixpkgs, flake-utils, rust-overlay }:
    flake-utils.lib.eachDefaultSystem
      (system:
        let
          overlays = [ (import rust-overlay) ];
          pkgs = import nixpkgs {
            inherit system overlays;
          };
          rustToolchain = pkgs.pkgsBuildHost.rust-bin.fromRustupToolchainFile ./rust-toolchain.toml;
          nativeBuildInputs = with pkgs; [ rustToolchain pkg-config ];
          buildInputs = with pkgs; [
            openssl
          ];
          python = pkgs.python310.override {
            packageOverrides = self: super: {
              jinja2-cli = self.buildPythonPackage rec {
                pname = "jinja2-cli";
                version = "0.8.2";

                src = self.fetchPypi {
                  inherit version pname;
                  sha256 = "sha256-oWuxRUEREo4gb1aMlZOM3vW1oTmSk3j3K7jPYXnhjlA=";
                };
                propagatedBuildInputs = [ pkgs.python310Packages.jinja2  pkgs.python310Packages.pytest pkgs.python310Packages.flake8 ];
              };
            };
          };
          python310Packages = python.pkgs;
					beku = python310Packages.buildPythonApplication rec {
						pname = "beku-stackabletech";
						version = "0.0.7";
						src = pkgs.fetchFromGitHub {
							owner = "stackabletech";
							repo = "beku.py";
							rev = "${version}";
							sha256 = "sha256-pz/OoMAEcMxoy66iBGATZ6XUpIeCX/nCRUFVjn8tglM=";
						};
						propagatedBuildInputs = [
							python310Packages.jinja2
							python310Packages.pyyaml
						];
						postConfigure = ''
							echo -e "from setuptools import setup\nsetup()" > setup.py
						'';
					};
        in
        with pkgs;
        {
          devShells.default = mkShell {
            inherit nativeBuildInputs;
            buildInputs = buildInputs ++ [kuttl beku python310 python310Packages.pip python310Packages.virtualenv python310Packages.jinja2 python.pkgs.jinja2-cli];
          };
        }
      );
}
